/* Copyright (c) 2026 Minefed. SPDX-License-Identifier: MIT */
package audit;

import com.mojang.brigadier.Command;
import io.netty.buffer.ByteBuf;
import io.netty.channel.*;
import net.fabricmc.api.DedicatedServerModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.networking.v1.ServerLoginConnectionEvents;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.minecraft.*;
import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.file.*;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;
import java.util.function.Supplier;

/**
 * Test-server-only packet counter. It observes the Netty pipeline and never
 * changes, delays or re-encodes a packet. Never include it in a release pack.
 */
public final class PacketStats implements DedicatedServerModInitializer {
    private static final Path OUTPUT = Path.of("packet-stats");
    private static final int DUMP_TICKS = Integer.getInteger("packetstats.dumpSeconds", 60) * 20;
    private static final String WIRE_OUT = "minefed_stats_wire", WIRE_IN = "minefed_stats_wire_in";
    private static final String PLAIN_OUT = "minefed_stats_plain", PLAIN_IN = "minefed_stats_plain_in";
    private static final String TYPE_OUT = "minefed_stats_type", TYPE_IN = "minefed_stats_type_in";

    /** direction, packet type, custom payload channel -> [count, uncompressed bytes]. */
    private static final Map<String, LongAdder[]> PACKETS = new ConcurrentHashMap<>();
    /** direction, player -> framed bytes on the socket (compressed when compression is enabled). */
    private static final Map<String, LongAdder> WIRE = new ConcurrentHashMap<>();
    private static final Map<String, String> NAMES = loadNames();
    private static volatile long windowStart = System.nanoTime();
    private static int ticks;

    @Override public void onInitializeServer() {
        ServerLoginConnectionEvents.INIT.register((handler, server) -> attach(connectionOf(handler), "login"));
        ServerPlayConnectionEvents.JOIN.register((handler, sender, server) ->
                attach(connectionOf(handler), handler.field_14140.method_7334().getName()));
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (++ticks >= DUMP_TICKS) { ticks = 0; dump("interval"); }
        });
        ServerLifecycleEvents.SERVER_STOPPING.register(server -> dump("stop"));
        CommandRegistrationCallback.EVENT.register((dispatcher, registry, environment) -> dispatcher.register(
                class_2170.method_9247("packetstats").requires(source -> source.method_9259(4))
                        .then(class_2170.method_9247("dump").executes(context -> { dump("command"); return Command.SINGLE_SUCCESS; }))
                        .then(class_2170.method_9247("reset").executes(context -> { reset(); return Command.SINGLE_SUCCESS; }))));
    }

    private static class_2535 connectionOf(Object handler) {
        return fieldOfType(handler, class_2535.class);
    }

    /** Reads the first field of the given type; avoids depending on private intermediary field names. */
    private static <T> T fieldOfType(Object owner, Class<T> fieldType) {
        for (Class<?> type = owner.getClass(); type != null; type = type.getSuperclass()) {
            for (Field field : type.getDeclaredFields()) {
                if (field.getType() == fieldType) {
                    try { field.setAccessible(true); return fieldType.cast(field.get(owner)); }
                    catch (ReflectiveOperationException error) { throw new IllegalStateException(error); }
                }
            }
        }
        throw new IllegalStateException("No " + fieldType.getSimpleName() + " in " + owner.getClass().getName());
    }

    private static void attach(class_2535 connection, String player) {
        Channel channel = fieldOfType(connection, Channel.class);
        if (channel == null) return; // local/in-memory connections have no socket
        channel.eventLoop().execute(() -> {
            ChannelPipeline pipeline = channel.pipeline();
            for (String name : List.of(WIRE_OUT, WIRE_IN, PLAIN_OUT, PLAIN_IN, TYPE_OUT, TYPE_IN)) {
                if (pipeline.get(name) != null) pipeline.remove(name);
            }
            if (pipeline.get("encoder") == null || pipeline.get("decoder") == null) return;
            Observer observer = new Observer(player);
            pipeline.addFirst(WIRE_OUT, observer.wireOut());
            pipeline.addFirst(WIRE_IN, observer.wireIn());
            pipeline.addBefore("encoder", PLAIN_OUT, observer.plainOut());
            pipeline.addBefore("decoder", PLAIN_IN, observer.plainIn());
            pipeline.addAfter("encoder", TYPE_OUT, observer.typeOut());
            pipeline.addAfter("decoder", TYPE_IN, observer.typeIn());
        });
    }

    /** Keeps a plain-byte observer between (de)compression and the codec when compression starts later. */
    private static void keepInside(ChannelPipeline pipeline, String observer, String compression, Supplier<ChannelHandler> handler) {
        if (pipeline.get(compression) == null || pipeline.get(observer) == null) return;
        List<String> names = pipeline.names();
        if (names.indexOf(observer) < names.indexOf(compression)) {
            pipeline.remove(observer);
            pipeline.addAfter(compression, observer, handler.get());
        }
    }

    private static final class Observer {
        private final String player;
        private int lastPlainIn;
        private String pendingOut;

        Observer(String player) { this.player = player; }

        ChannelHandler wireOut() {
            return new ChannelOutboundHandlerAdapter() {
                @Override public void write(ChannelHandlerContext ctx, Object msg, ChannelPromise promise) throws Exception {
                    if (msg instanceof ByteBuf buf) WIRE.computeIfAbsent("out\t" + player, k -> new LongAdder()).add(buf.readableBytes());
                    super.write(ctx, msg, promise);
                }
            };
        }

        ChannelHandler wireIn() {
            return new ChannelInboundHandlerAdapter() {
                @Override public void channelRead(ChannelHandlerContext ctx, Object msg) throws Exception {
                    if (msg instanceof ByteBuf buf) WIRE.computeIfAbsent("in\t" + player, k -> new LongAdder()).add(buf.readableBytes());
                    super.channelRead(ctx, msg);
                }
            };
        }

        ChannelHandler plainOut() {
            return new ChannelOutboundHandlerAdapter() {
                @Override public void write(ChannelHandlerContext ctx, Object msg, ChannelPromise promise) throws Exception {
                    if (msg instanceof ByteBuf buf && pendingOut != null) {
                        record(pendingOut, buf.readableBytes());
                        pendingOut = null;
                    }
                    super.write(ctx, msg, promise);
                }
            };
        }

        ChannelHandler plainIn() {
            return new ChannelInboundHandlerAdapter() {
                @Override public void channelRead(ChannelHandlerContext ctx, Object msg) throws Exception {
                    if (msg instanceof ByteBuf buf) lastPlainIn = buf.readableBytes();
                    super.channelRead(ctx, msg);
                }
            };
        }

        ChannelHandler typeOut() {
            return new ChannelOutboundHandlerAdapter() {
                @Override public void write(ChannelHandlerContext ctx, Object msg, ChannelPromise promise) throws Exception {
                    keepInside(ctx.pipeline(), PLAIN_OUT, "compress", Observer.this::plainOut);
                    pendingOut = "out\t" + describe(msg);
                    super.write(ctx, msg, promise);
                }
            };
        }

        ChannelHandler typeIn() {
            return new ChannelInboundHandlerAdapter() {
                @Override public void channelRead(ChannelHandlerContext ctx, Object msg) throws Exception {
                    keepInside(ctx.pipeline(), PLAIN_IN, "decompress", Observer.this::plainIn);
                    record("in\t" + describe(msg), lastPlainIn);
                    lastPlainIn = 0;
                    super.channelRead(ctx, msg);
                }
            };
        }
    }

    private static String describe(Object packet) {
        String type = NAMES.getOrDefault(packet.getClass().getName(), packet.getClass().getName());
        class_8710 payload = packet instanceof class_2658 s2c ? s2c.comp_1646()
                : packet instanceof class_2817 c2s ? c2s.comp_1647() : null;
        return type + "\t" + (payload == null ? "" : String.valueOf(payload.comp_1678()));
    }

    private static void record(String key, int bytes) {
        LongAdder[] values = PACKETS.computeIfAbsent(key, k -> new LongAdder[] {new LongAdder(), new LongAdder()});
        values[0].increment();
        values[1].add(bytes);
    }

    private static synchronized void dump(String reason) {
        double seconds = Math.max(1e-9, (System.nanoTime() - windowStart) / 1e9);
        StringBuilder out = new StringBuilder("# reason=" + reason + " windowSeconds=" + String.format(Locale.ROOT, "%.3f", seconds) + "\n");
        out.append("direction\ttype\tchannel\tcount\tuncompressedBytes\tcountPerSecond\tbytesPerSecond\n");
        new TreeMap<>(PACKETS).forEach((key, values) -> out.append(key).append('\t').append(values[0].sum()).append('\t')
                .append(values[1].sum()).append('\t').append(rate(values[0].sum(), seconds)).append('\t')
                .append(rate(values[1].sum(), seconds)).append('\n'));
        out.append("\ndirection\tplayer\twireBytes\twireBytesPerSecond\n");
        new TreeMap<>(WIRE).forEach((key, value) -> out.append(key).append('\t').append(value.sum()).append('\t')
                .append(rate(value.sum(), seconds)).append('\n'));
        try {
            Files.createDirectories(OUTPUT);
            String stamp = LocalDateTime.now(ZoneOffset.UTC).format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss"));
            Files.writeString(OUTPUT.resolve(stamp + "-" + reason + ".tsv"), out);
        } catch (IOException error) {
            error.printStackTrace();
        }
    }

    private static String rate(long value, double seconds) {
        return String.format(Locale.ROOT, "%.2f", value / seconds);
    }

    private static synchronized void reset() {
        PACKETS.clear();
        WIRE.clear();
        windowStart = System.nanoTime();
    }

    /** Optional Yarn tiny v2 file for readable packet names: -Dpacketstats.mappings=/path/mappings.tiny */
    private static Map<String, String> loadNames() {
        String path = System.getProperty("packetstats.mappings");
        Map<String, String> names = new HashMap<>();
        if (path == null) return names;
        try {
            for (String line : Files.readAllLines(Path.of(path))) {
                String[] parts = line.split("\t");
                if (parts.length >= 3 && parts[0].equals("c")) {
                    names.put(parts[1].replace('/', '.'), parts[parts.length - 1].substring(parts[parts.length - 1].lastIndexOf('/') + 1));
                }
            }
        } catch (IOException error) {
            error.printStackTrace();
        }
        return names;
    }
}
