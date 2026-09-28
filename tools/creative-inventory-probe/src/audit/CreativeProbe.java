/* Copyright (c) 2026 Minefed. SPDX-License-Identifier: MIT */
package audit;

import net.fabricmc.api.ClientModInitializer;
import net.minecraft.*;
import java.lang.reflect.Method;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Test-only probe. Launch only in a fresh disposable offline game directory. */
public final class CreativeProbe implements ClientModInitializer {
    private static final Path RESULT = Path.of("creative-probe.tsv");
    private static final int TIMEOUT_MINUTES = 15;
    private interface Task<T> { T run() throws Exception; }

    private static <T> T onMain(class_310 client, Task<T> task) throws Exception {
        CompletableFuture<T> result = new CompletableFuture<>();
        client.execute(() -> {
            try { result.complete(task.run()); }
            catch (Throwable error) { result.completeExceptionally(error); }
        });
        return result.get(TIMEOUT_MINUTES, TimeUnit.MINUTES);
    }

    private static void record(String text) throws Exception {
        Files.writeString(RESULT, text + "\n", StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        System.out.println("CREATIVE_PROBE " + text);
    }

    @Override public void onInitializeClient() {
        Thread worker = new Thread(() -> {
            class_310 client = class_310.method_1551();
            try {
                if (Files.exists(RESULT)) throw new IllegalStateException("Use a fresh audit directory");
                boolean existing = Boolean.getBoolean("audit.reuseWorld");
                awaitReady(client, existing);
                if (!existing) createWorld(client);
                sweep(client, "cold");
                verifyDiagonalExclusions(client);
                if (Boolean.getBoolean("audit.verifyWikipedia")) verifyWikipediaArticles();
                if (!Boolean.getBoolean("audit.skipReload")) {
                    CompletableFuture<?> reload = onMain(client, client::method_1521);
                    reload.get(TIMEOUT_MINUTES, TimeUnit.MINUTES);
                    awaitReady(client, true);
                    sweep(client, "reload");
                }
                record("complete\ttrue");
            } catch (Throwable error) {
                error.printStackTrace();
                try { record("failed\t" + error.getClass().getName()); }
                catch (Exception writeFailure) { writeFailure.printStackTrace(); }
            } finally {
                client.execute(client::method_1490);
            }
        }, "Creative-inventory-audit");
        worker.setDaemon(true);
        worker.start();
    }

    private static void awaitReady(class_310 client, boolean world) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.MINUTES.toNanos(TIMEOUT_MINUTES);
        while (System.nanoTime() < deadline) {
            if (onMain(client, () -> client.method_18506() == null &&
                    (world ? client.field_1724 != null : client.field_1755 instanceof class_442))) return;
            Thread.sleep(250);
        }
        throw new TimeoutException(world ? "World did not load" : "Title did not load");
    }

    private static void createWorld(class_310 client) throws Exception {
        onMain(client, () -> { class_525.method_31130(client, client.field_1755); return null; });
        long deadline = System.nanoTime() + TimeUnit.MINUTES.toNanos(TIMEOUT_MINUTES);
        boolean started = false;
        while (!started && System.nanoTime() < deadline) {
            started = onMain(client, () -> {
                if (!(client.field_1755 instanceof class_525 screen)) return false;
                screen.method_48657().method_48704(class_8100.class_4539.field_20626);
                Method create = class_525.class.getDeclaredMethod("method_2736");
                create.setAccessible(true);
                create.invoke(screen);
                return true;
            });
            if (!started) Thread.sleep(250);
        }
        if (!started) throw new TimeoutException("Create-world screen did not load");
        awaitReady(client, true);
    }

    private static void sweep(class_310 client, String pass) throws Exception {
        InventorySweep screen = onMain(client, () -> {
            class_7706.method_47330(class_7701.field_40183, true, client.field_1687.method_30349());
            List<class_1799> stacks = new ArrayList<>(class_7706.method_47344().method_45414());
            List<String> labels = stacks.stream()
                .map(stack -> class_7923.field_41178.method_10221(stack.method_7909()).toString()).toList();
            record(pass + "\tcreative_stacks\t" + stacks.size());
            // Do not query baked models or quads here: that can prewarm the bug.
            record(pass + "\tmodels_not_prewarmed\ttrue");
            Files.write(Path.of(pass + "-creative-items.txt"), labels);
            List<String> items = new ArrayList<>(), blocks = new ArrayList<>();
            class_7923.field_41178.forEach(item -> items.add(class_7923.field_41178.method_10221(item).toString()));
            class_7923.field_41175.forEach(block -> blocks.add(class_7923.field_41175.method_10221(block).toString()));
            Files.write(Path.of(pass + "-registry-items.txt"), items);
            Files.write(Path.of(pass + "-registry-blocks.txt"), blocks);
            InventorySweep audit = new InventorySweep(stacks, labels, pass);
            client.method_1507(audit);
            return audit;
        });
        screen.done.get(TIMEOUT_MINUTES, TimeUnit.MINUTES);
        record(pass + "_sweep_complete\t" + screen.stackCount());
    }

    private static void verifyDiagonalExclusions(class_310 client) throws Exception {
        onMain(client, () -> {
            class_6862<class_2248> excluded = class_6862.method_40092(
                class_7924.field_41254, new class_2960("diagonalfences", "non_diagonal_fences"));
            List<String> results = new ArrayList<>();
            for (class_2248 block : class_7923.field_41175) {
                String id = class_7923.field_41175.method_10221(block).toString();
                if (id.startsWith("mcwfences:") && id.endsWith("_grass_topped_wall")) {
                    boolean present = block.method_9564().method_26164(excluded);
                    results.add(id + "\t" + present);
                }
            }
            Files.write(Path.of("non-diagonal-fences.tsv"), results);
            if (results.stream().anyMatch(line -> line.endsWith("\tfalse")))
                throw new IllegalStateException("Unsupported Macaw walls are missing their diagonal exclusion tag");
            record("diagonal_exclusions\t" + results.size());
            return null;
        });
    }

    private static void verifyWikipediaArticles() throws Exception {
        Class<?> wiki = Class.forName("de.mrjulsen.mcdragonlib.util.Wikipedia");
        List<String> rows = new ArrayList<>();
        for (String id : List.of("Q8004", "Q2354774")) {
            Object article = wiki.getMethod("getArticle", String.class).invoke(null, id);
            if (article == null || !(boolean) article.getClass().getMethod("isLoaded").invoke(article))
                throw new IllegalStateException("Wikipedia article did not finish: " + id);
            var languagesField = article.getClass().getDeclaredField("articleLanguages");
            languagesField.setAccessible(true);
            int count = ((Map<?, ?>) languagesField.get(article)).size();
            if (count == 0) throw new IllegalStateException("Wikipedia article has no sitelinks: " + id);
            rows.add(id + "\t" + count);
        }
        Files.write(Path.of("wikipedia-articles.tsv"), rows);
        record("wikipedia_articles\t" + rows.size());
    }
}
