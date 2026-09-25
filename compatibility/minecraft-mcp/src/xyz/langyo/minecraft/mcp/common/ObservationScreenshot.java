/* Minefed Minecraft 1.20.4 framebuffer capture. MIT; see LICENSE-MIT. */
package xyz.langyo.minecraft.mcp.common;

import java.lang.reflect.Method;
import java.util.Base64;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;

public final class ObservationScreenshot {
    private ObservationScreenshot() {}

    public static String capture(Object client) throws Exception {
        if (!(client instanceof Executor)) throw new IllegalStateException("client_unavailable");
        CompletableFuture<byte[]> result = new CompletableFuture<>();
        ((Executor) client).execute(() -> {
            try {
                Object framebuffer = invoke(client, "getFramebuffer", "method_1522");
                ClassLoader loader = client.getClass().getClassLoader();
                Class<?> recorder;
                String method;
                try {
                    recorder = Class.forName("net.minecraft.class_318", true, loader);
                    method = "method_1663";
                } catch (ClassNotFoundException namedRuntime) {
                    recorder = Class.forName("net.minecraft.client.util.ScreenshotRecorder", true, loader);
                    method = "takeScreenshot";
                }
                Method capture = null;
                for (Method candidate : recorder.getMethods()) {
                    if (candidate.getName().equals(method) && candidate.getParameterCount() == 1
                            && candidate.getParameterTypes()[0].isInstance(framebuffer)) {
                        capture = candidate;
                        break;
                    }
                }
                if (capture == null) throw new NoSuchMethodException(method);
                Object image = capture.invoke(null, framebuffer);
                try { result.complete((byte[]) invoke(image, "getBytes", "method_24036")); }
                finally { ((AutoCloseable) image).close(); }
            } catch (Exception error) {
                result.completeExceptionally(error);
            }
        });
        return "data:image/png;base64," + Base64.getEncoder().encodeToString(result.get(10, TimeUnit.SECONDS));
    }

    private static Object invoke(Object target, String named, String intermediary) throws Exception {
        try { return target.getClass().getMethod(named).invoke(target); }
        catch (NoSuchMethodException missing) { return target.getClass().getMethod(intermediary).invoke(target); }
    }
}
