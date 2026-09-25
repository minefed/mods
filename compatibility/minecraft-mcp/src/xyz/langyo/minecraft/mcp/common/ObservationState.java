/* Minefed observation queries for Minecraft 1.20.4. MIT; see LICENSE-MIT.
 * Exact Yarn 1.20.4+build.3/intermediary names; never guess fields by type.
 */
package xyz.langyo.minecraft.mcp.common;

import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Locale;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;

public final class ObservationState {
    private ObservationState() {}

    public static String query(String command, Object client) {
        if (client == null) return unavailable("client_unavailable");
        if (!(client instanceof Executor)) return unavailable("client_executor_unavailable");
        CompletableFuture<String> result = new CompletableFuture<>();
        ((Executor) client).execute(() -> result.complete(snapshot(command, client)));
        try { return result.get(5, TimeUnit.SECONDS); }
        catch (Exception error) { return unavailable("client_query_timed_out"); }
    }

    static String snapshot(String command, Object client) {
        try {
            Object player = field(client, "player", "field_1724");
            Object world = field(client, "world", "field_1687");
            if (player == null || world == null) return unavailable("not_in_world");
            Object interaction = field(client, "interactionManager", "field_1761");
            if (interaction == null) return unavailable("interaction_manager_unavailable");
            String gameMode = (String) call(call(interaction, "getCurrentGameMode", "method_2920"), "getName", "method_8381");
            Object key = call(world, "getRegistryKey", "method_27983");
            String dimension = call(key, "getValue", "method_29177").toString();
            JsonObject data = new JsonObject();
            data.addProperty("available", true);
            data.addProperty("dimension", dimension);
            if (command.equals("get_player_info")) {
                Object profile = call(player, "getGameProfile", "method_7334");
                String name = (String) call(profile, "getName", "getName");
                double x = number(player, "getX", "method_23317");
                double y = number(player, "getY", "method_23318");
                double z = number(player, "getZ", "method_23321");
                double yaw = number(player, "getYaw", "method_36454");
                double pitch = number(player, "getPitch", "method_36455");
                data.addProperty("name", name);
                data.addProperty("x", x); data.addProperty("y", y); data.addProperty("z", z);
                data.addProperty("yaw", yaw); data.addProperty("pitch", pitch);
                data.addProperty("pos", String.format(Locale.ROOT, "%.3f %.3f %.3f", x, y, z));
                data.addProperty("rotation", String.format(Locale.ROOT, "%.3f %.3f", yaw, pitch));
                data.addProperty("health", number(player, "getHealth", "method_6032"));
                data.addProperty("gamemode", gameMode);
                data.addProperty("food", number(call(player, "getHungerManager", "method_7344"), "getFoodLevel", "method_7586"));
            } else if (command.equals("get_world_info")) {
                data.addProperty("difficulty", (String) call(call(world, "getDifficulty", "method_8407"), "getName", "method_5460"));
                data.addProperty("gametype", gameMode);
                data.addProperty("time", ((Number) call(world, "getTimeOfDay", "method_8532")).longValue());
                data.addProperty("game_time", ((Number) call(world, "getTime", "method_8510")).longValue());
                boolean raining = (Boolean) call(world, "isRaining", "method_8419");
                boolean thundering = (Boolean) call(world, "isThundering", "method_8546");
                data.addProperty("weather", thundering ? "thunder" : raining ? "rain" : "clear");
                Object server = call(client, "getServer", "method_1576");
                if (server == null) {
                    data.add("world_name", JsonNull.INSTANCE);
                    data.addProperty("world_name_available", false);
                } else {
                    Object properties = call(server, "getSaveProperties", "method_27728");
                    data.addProperty("world_name", (String) call(properties, "getLevelName", "method_150"));
                    data.addProperty("world_name_available", true);
                }
            } else return unavailable("unsupported_observation");
            return data.toString();
        } catch (ReflectiveOperationException | RuntimeException error) {
            return unavailable("unsupported_client_state");
        }
    }

    private static String unavailable(String reason) {
        JsonObject result = new JsonObject();
        result.addProperty("available", false);
        result.addProperty("error", reason);
        return result.toString();
    }

    private static Object field(Object target, String named, String intermediary) throws ReflectiveOperationException {
        for (String name : new String[]{named, intermediary}) {
            for (Class<?> type = target.getClass(); type != null; type = type.getSuperclass()) {
                try { Field field = type.getDeclaredField(name); field.setAccessible(true); return field.get(target); }
                catch (NoSuchFieldException ignored) {}
            }
        }
        throw new NoSuchFieldException(intermediary);
    }

    private static Object call(Object target, String named, String intermediary) throws ReflectiveOperationException {
        for (String name : new String[]{named, intermediary}) {
            try { Method method = target.getClass().getMethod(name); method.setAccessible(true); return method.invoke(target); }
            catch (NoSuchMethodException ignored) {}
        }
        throw new NoSuchMethodException(intermediary);
    }

    private static double number(Object target, String named, String intermediary) throws ReflectiveOperationException {
        double value = ((Number) call(target, named, intermediary)).doubleValue();
        if (!Double.isFinite(value)) throw new IllegalArgumentException("nonfinite state");
        return value;
    }
}
