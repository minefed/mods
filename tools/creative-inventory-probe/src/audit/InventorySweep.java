/* Copyright (c) 2026 Minefed. SPDX-License-Identifier: MIT */
package audit;

import net.minecraft.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.CompletableFuture;

/** Draws actual GUI item models before querying their textures or quads. */
public final class InventorySweep extends class_437 {
    public final CompletableFuture<Void> done = new CompletableFuture<>();
    private final List<class_1799> stacks;
    private final List<String> labels;
    private final String pass;
    private int page, frame;

    public InventorySweep(List<class_1799> stacks, List<String> labels, String pass) {
        super(class_2561.method_43470("Creative inventory render audit"));
        this.stacks = stacks;
        this.labels = labels;
        this.pass = pass;
    }
    public int stackCount() { return stacks.size(); }
    private Path output(String name) { return Path.of(pass + "-" + name); }
    private void append(String name, String line) throws Exception {
        Files.writeString(output(name), line + "\n", StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }

    @Override public void method_25394(class_332 context, int mouseX, int mouseY, float delta) {
        if (done.isDone()) return;
        try {
            if (field_22789 < 1220 || field_22790 < 680)
                throw new IllegalStateException("Use a window at least 1220x680 and GUI scale 1");
            context.method_25294(0, 0, field_22789, field_22790, 0xff344253);
            int start = page * 48, end = Math.min(start + 48, stacks.size());
            for (int index = start; index < end; index++) {
                int slot = index - start, x = 8 + (slot % 8) * 150, y = 8 + (slot / 8) * 108;
                context.method_51448().method_22903();
                try {
                    context.method_51448().method_22904(x + 40, y + 4, 0);
                    context.method_51448().method_22905(4, 4, 4);
                    context.method_51427(stacks.get(index), 0, 0);
                } catch (Throwable error) {
                    append("render-errors.tsv", index + "\t" + labels.get(index) + "\t" + error.getClass().getName());
                    throw error;
                } finally { context.method_51448().method_22909(); }
                String label = labels.get(index);
                context.method_25303(class_310.method_1551().field_1772,
                    index + " " + label.substring(0, Math.min(19, label.length())), x, y + 78, 0xffffffff);
            }
            context.method_51452();
            frame++;
            if (frame == 1 || frame == 3) {
                try (class_1011 image = class_318.method_1663(class_310.method_1551().method_1522())) {
                    boolean save = page == 0;
                    for (int index = start; index < end; index++) {
                        int slot = index - start, x = 8 + (slot % 8) * 150, y = 8 + (slot / 8) * 108, count = 0;
                        for (int px = x; px < x + 145; px++) for (int py = y; py < y + 76; py++) {
                            int pixel = image.method_4315(px, py), r = pixel & 255, g = (pixel >> 8) & 255, b = (pixel >> 16) & 255;
                            if (r > 100 && b > 100 && g < 6 && Math.abs(r - b) < 4) count++;
                        }
                        if (count > 5) {
                            save = true;
                            append("render-candidates.tsv", page + "\t" + frame + "\t" + index + "\t" + labels.get(index) + "\t" + count);
                        }
                        if (labels.get(index).startsWith("pfm:") && labels.get(index).endsWith("_herringbone_planks")) save = true;
                    }
                    if (save) image.method_4314(output("page-" + page + "-frame-" + frame + ".png"));
                }
            }
            if (frame == 3) {
                append("sweep-progress.tsv", page + "\t" + start + "\t" + end);
                frame = 0;
                page++;
                if (end == stacks.size()) done.complete(null);
            }
        } catch (Throwable error) {
            error.printStackTrace();
            done.completeExceptionally(error);
        }
    }
}
