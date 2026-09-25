/* Minecraft 1.20.4 / Yarn 1.20.4+build.3 input compatibility. MIT; see LICENSE-MIT. */
package xyz.langyo.minecraft.mcp.common;

import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.*;

/** Executes exact mapped operations on the client thread without sleeping on it. */
public final class GameplayControl {
    private static final ScheduledExecutorService RELEASES = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "Minefed-MCP-KeyRelease"); t.setDaemon(true); return t;
    });
    // Access only on the client thread. Tokens prevent an earlier hold releasing a later one.
    private static final Map<Integer, Object> HELD = new HashMap<>();
    private static final Set<String> COMMANDS = Set.of("press_key", "set_view_angle", "look_delta",
        "right_click", "use_item", "place_block", "execute_command", "set_gamemode", "close_screen", "release_all_keys");
    private GameplayControl() {}

    public static String dispatch(String command, Map<String, String> params, Object client) {
        if (!COMMANDS.contains(command)) return null;
        if (!(client instanceof Executor)) return error("client_executor_unavailable");
        CompletableFuture<String> result = new CompletableFuture<>();
        ((Executor) client).execute(() -> {
            // Do not execute a queued world mutation after the HTTP caller timed out.
            if (result.isCancelled()) return;
            try { result.complete(run(command, params, client)); }
            catch (Exception e) { result.complete(error(e.toString())); }
        });
        try { return result.get(5, TimeUnit.SECONDS); }
        catch (Exception e) { result.cancel(false); return error("client_action_timed_out; inspect state before retrying"); }
    }

    private static String run(String command, Map<String, String> p, Object client) throws Exception {
        if (command.equals("release_all_keys")) {
            for (int code : new ArrayList<>(HELD.keySet())) key(client, code, 0);
            HELD.clear();
            return json(Map.of("released", true));
        }
        if (command.equals("press_key")) {
            String name = p.get("key");
            int code = keyCode(name == null ? "" : name);
            if (code < 0) throw new IllegalArgumentException("unknown key: " + name);
            double seconds = Double.parseDouble(p.getOrDefault("hold_seconds", "0"));
            if (!Double.isFinite(seconds) || seconds < 0 || seconds > Long.MAX_VALUE / 1000.0)
                throw new IllegalArgumentException("invalid hold_seconds");
            long millis = Math.max(50, (long) (seconds * 1000));
            Object token = new Object();
            key(client, code, 1);
            HELD.put(code, token);
            RELEASES.schedule(() -> ((Executor) client).execute(() -> {
                if (HELD.get(code) != token) return;
                try { key(client, code, 0); HELD.remove(code); }
                catch (Exception e) { System.err.println("[Minefed MCP] Key release failed: " + e); }
            }), millis, TimeUnit.MILLISECONDS);
            return json(Map.of("pressed", name, "release_after_ms", millis, "completed", false));
        }
        if (command.equals("close_screen")) {
            invoke(client, "setScreen", "method_1507", new Object[]{null});
            return json(Map.of("screen_closed", true));
        }
        Object player = field(client, "player", "field_1724");
        if (player == null) return error("not_in_world");
        if (command.equals("set_view_angle") || command.equals("look_delta")) {
            boolean delta = command.equals("look_delta");
            float yaw = finite(p.get(delta ? "delta_yaw" : "yaw"));
            float pitch = finite(p.get(delta ? "delta_pitch" : "pitch"));
            if (delta) {
                yaw += ((Number) invoke(player, "getYaw", "method_36454")).floatValue();
                pitch += ((Number) invoke(player, "getPitch", "method_36455")).floatValue();
            }
            yaw = ((yaw % 360) + 540) % 360 - 180;
            pitch = Math.max(-90, Math.min(90, pitch));
            invoke(player, "setYaw", "method_36456", yaw);
            invoke(player, "setPitch", "method_36457", pitch);
            return json(Map.of("yaw", yaw, "pitch", pitch));
        }
        if (command.equals("execute_command") || command.equals("set_gamemode")) {
            String value = command.equals("set_gamemode") ? "gamemode " + p.get("mode") : p.get("command");
            if (value == null || value.isBlank()) throw new IllegalArgumentException("missing command");
            String slashless = value.startsWith("/") ? value.substring(1) : value;
            Object network = invoke(client, "getNetworkHandler", "method_1562");
            if (network == null) return error("not_connected");
            invoke(network, "sendChatCommand", "method_45730", slashless);
            return json(Map.of("sent", true, "command", slashless, "server_success_verified", false));
        }
        // Keep GUI right-click behavior upstream. World use/place goes through vanilla interaction.
        if (field(client, "currentScreen", "field_1755") != null) {
            if (command.equals("right_click")) return ReflectionHelper.doRightClick(client);
            return error("close the current screen before using or placing an item");
        }
        invoke(client, "doItemUse", "method_1583");
        return json(Map.of("submitted", command, "world_change_verified", false));
    }

    private static void key(Object client, int code, int action) throws Exception {
        Object keyboard = field(client, "keyboard", "field_1774");
        Object window = invoke(client, "getWindow", "method_22683");
        long handle = ((Number) invoke(window, "getHandle", "method_4490")).longValue();
        invoke(keyboard, "onKey", "method_1466", handle, code, 0, action, 0);
    }

    private static float finite(String value) {
        float number = Float.parseFloat(value);
        if (!Float.isFinite(number)) throw new IllegalArgumentException("angle must be finite");
        return number;
    }
    private static int keyCode(String value) {
        String key = value.toLowerCase(Locale.ROOT).replace("key.keyboard.", "").replace('.', '_').replace(' ', '_');
        if (key.length() == 1) {
            char c = Character.toUpperCase(key.charAt(0));
            if ((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) return c;
        }
        if (key.matches("f([1-9]|1[0-9]|2[0-5])")) return 289 + Integer.parseInt(key.substring(1));
        return switch (key) {
            case "space" -> 32; case "apostrophe", "'" -> 39; case "comma", "," -> 44;
            case "minus", "-" -> 45; case "period", "." -> 46; case "slash", "/" -> 47;
            case "semicolon", ";" -> 59; case "equal", "=" -> 61;
            case "left_bracket", "[" -> 91; case "backslash", "\\" -> 92;
            case "right_bracket", "]" -> 93; case "grave_accent", "`" -> 96;
            case "escape", "esc" -> 256; case "enter", "return" -> 257; case "tab" -> 258;
            case "backspace" -> 259; case "insert" -> 260; case "delete" -> 261;
            case "right" -> 262; case "left" -> 263; case "down" -> 264; case "up" -> 265;
            case "page_up" -> 266; case "page_down" -> 267; case "home" -> 268; case "end" -> 269;
            case "caps_lock" -> 280; case "scroll_lock" -> 281; case "num_lock" -> 282;
            case "print_screen" -> 283; case "pause" -> 284;
            case "shift", "left_shift" -> 340; case "control", "ctrl", "left_control" -> 341;
            case "alt", "left_alt" -> 342; case "left_win", "left_super" -> 343;
            case "right_shift" -> 344; case "right_control" -> 345; case "right_alt" -> 346;
            case "right_win", "right_super" -> 347; case "menu" -> 348;
            default -> -1;
        };
    }
    private static String json(Object value) { return McpProtocol.GSON.toJson(value); }
    private static String error(String message) { return json(Map.of("error", message)); }
    private static Object field(Object target, String named, String intermediary) throws Exception {
        for (String name : new String[]{named, intermediary}) {
            for (Class<?> type = target.getClass(); type != null; type = type.getSuperclass()) {
                try { Field f = type.getDeclaredField(name); f.setAccessible(true); return f.get(target); }
                catch (NoSuchFieldException ignored) {}
            }
        }
        throw new NoSuchFieldException(intermediary);
    }
    private static Object invoke(Object target, String named, String intermediary, Object... args) throws Exception {
        for (String name : new String[]{named, intermediary}) {
            for (Class<?> type = target.getClass(); type != null; type = type.getSuperclass()) {
                for (Method m : type.getDeclaredMethods()) {
                    if (m.getName().equals(name) && m.getParameterCount() == args.length) {
                        m.setAccessible(true); return m.invoke(target, args);
                    }
                }
            }
        }
        throw new NoSuchMethodException(intermediary);
    }
}
