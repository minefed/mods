package xyz.langyo.minecraft.mcp.common;

import java.util.*;
import java.util.concurrent.*;

/** Intermediary-only fake client: verifies input timing and exact 1.20.4 member names. */
public class ControlProbe {
    public static class Client implements Executor, AutoCloseable {
        final ExecutorService thread = Executors.newSingleThreadExecutor();
        public final Player field_1724 = new Player();
        public final Keyboard field_1774 = new Keyboard();
        public Object field_1755;
        final Network network = new Network();
        int uses;
        public void execute(Runnable r) { thread.execute(r); }
        public Window method_22683() { return new Window(); }
        public Network method_1562() { return network; }
        private void method_1583() { uses++; }
        public void method_1507(Object screen) { field_1755 = screen; }
        public void close() { thread.shutdownNow(); }
    }
    public static class Keyboard {
        final List<Integer> actions = new CopyOnWriteArrayList<>();
        public void method_1466(long handle, int code, int scan, int action, int mods) {
            if (handle != 17 || code != 87) throw new AssertionError("wrong key/window");
            actions.add(action);
        }
    }
    public static class Window { public long method_4490() { return 17; } }
    public static class Player {
        float yaw, pitch;
        public float method_36454() { return yaw; }
        public float method_36455() { return pitch; }
        public void method_36456(float value) { yaw = value; }
        public void method_36457(float value) { pitch = value; }
    }
    public static class Network {
        String sent;
        public void method_45730(String value) { sent = value; }
    }
    static void check(boolean condition, String message) { if (!condition) throw new AssertionError(message); }
    static String run(Client client, String cmd, Map<String, String> params) {
        String result = GameplayControl.dispatch(cmd, params, client);
        check(result != null && !result.contains("\"error\""), String.valueOf(result));
        return result;
    }
    public static void main(String[] args) throws Exception {
        try (Client client = new Client()) {
            run(client, "press_key", Map.of("key", "key.keyboard.w", "hold_seconds", "0.4"));
            CountDownLatch tick = new CountDownLatch(1);
            client.execute(tick::countDown);
            check(tick.await(150, TimeUnit.MILLISECONDS), "key hold blocked client ticks");
            check(client.field_1774.actions.equals(List.of(1)), "key released too early");
            Thread.sleep(550);
            check(client.field_1774.actions.equals(List.of(1, 0)), "key did not release");
            run(client, "press_key", Map.of("key", "W", "hold_seconds", "0.4"));
            run(client, "release_all_keys", Map.of());
            int released = client.field_1774.actions.size();
            Thread.sleep(550);
            check(client.field_1774.actions.size() == released, "stale timer released another hold");
            run(client, "set_view_angle", Map.of("yaw", "90", "pitch", "-30"));
            run(client, "look_delta", Map.of("delta_yaw", "15", "delta_pitch", "10"));
            check(client.field_1724.yaw == 105 && client.field_1724.pitch == -20, "view did not change");
            run(client, "execute_command", Map.of("command", "/setblock 1 2 3 minecraft:stone"));
            check(client.network.sent.equals("setblock 1 2 3 minecraft:stone"), "command not sent");
            run(client, "place_block", Map.of());
            check(client.uses == 1, "vanilla use action not called");
            client.field_1755 = new Object();
            check(GameplayControl.dispatch("place_block", Map.of(), client).contains("error"), "GUI world action not reported");
            run(client, "close_screen", Map.of());
            check(client.field_1755 == null, "screen not closed");
            check(GameplayControl.dispatch("press_key", Map.of("key", "bad-key"), client).contains("error"), "bad key not reported");
            check(GameplayControl.dispatch("select_list_item", Map.of(), client) == null, "upstream dispatch blocked");
            System.out.println("CONTROL_OK: timed movement, key release, view, command, item use and GUI");
        }
    }
}
