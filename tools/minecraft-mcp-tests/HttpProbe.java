package xyz.langyo.minecraft.mcp.common;

import com.sun.net.httpserver.HttpServer;
import java.lang.reflect.Field;
import java.util.Map;

/** A real HTTP listener with a recording handler; never loads Minecraft. */
public final class HttpProbe {
    public static void main(String[] args) throws Exception {
        McpMessageHandler handler = new McpMessageHandler() {
            private int calls;
            @Override protected Object dispatch(String method, Map<String, String> params, Object client) {
                calls++;
                if (method.equals("screenshot")) return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9l8AAAAASUVORK5CYII=";
                return "{\"method\":\"" + method + "\",\"calls\":" + calls + "}";
            }
        };
        McpHttpServer server = new McpHttpServer(handler, Integer.parseInt(args[0]));
        server.start();
        Field field = McpHttpServer.class.getDeclaredField("server");
        field.setAccessible(true);
        System.out.println("BOUND " + ((HttpServer) field.get(server)).getAddress().getAddress().getHostAddress());
        System.out.flush();
        try { System.in.read(); }
        finally { server.stop(); }
    }
}
