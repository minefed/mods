package xyz.langyo.minecraft.mcp.common;

import java.util.Locale;
import java.util.concurrent.Executor;

/** Use intermediary names, non-default values and a comma-decimal locale. */
public final class StateProbe {
    public static class Client implements Executor {
        public Player field_1724;
        public World field_1687;
        public Interaction field_1761 = new Interaction();
        public Object method_1576() { return null; }
        public void execute(Runnable task) { task.run(); }
    }
    public static class Player {
        public Profile method_7334() { return new Profile(); }
        public double method_23317() { return 12.25; }
        public double method_23318() { return 80.5; }
        public double method_23321() { return -9.75; }
        public float method_36454() { return 135.5f; }
        public float method_36455() { return -30.25f; }
        public float method_6032() { return 17.5f; }
        public Hunger method_7344() { return new Hunger(); }
    }
    public static class Profile { public String getName() { return "Observer"; } }
    public static class Hunger { public int method_7586() { return 13; } }
    public static class Interaction { public Mode method_2920() { return new Mode(); } }
    public static class Mode { public String method_8381() { return "creative"; } }
    public static class Key { public String method_29177() { return "minecraft:the_nether"; } }
    public static class Difficulty { public String method_5460() { return "hard"; } }
    public static class World {
        public Key method_27983() { return new Key(); }
        public Difficulty method_8407() { return new Difficulty(); }
        public long method_8532() { return 13001; }
        public long method_8510() { return 77002; }
        public boolean method_8419() { return true; }
        public boolean method_8546() { return true; }
    }
    public static void main(String[] args) {
        Locale.setDefault(Locale.GERMANY);
        Client client = new Client();
        System.out.println(ObservationState.query("get_world_info", client));
        client.field_1724 = new Player(); client.field_1687 = new World();
        System.out.println(ObservationState.query("get_player_info", client));
        System.out.println(ObservationState.query("get_world_info", client));
        System.out.println(ObservationState.query("get_world_info", new Object()));
    }
}
