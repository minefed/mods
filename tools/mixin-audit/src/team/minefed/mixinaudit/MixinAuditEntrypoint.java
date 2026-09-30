package team.minefed.mixinaudit;

import net.fabricmc.loader.api.entrypoint.PreLaunchEntrypoint;
import org.spongepowered.asm.mixin.MixinEnvironment;

/**
 * Loads every Mixin target class so that all Mixins are applied, then exits before the game window opens.
 * A failing required Mixin throws during the audit; the process exit code reports the result.
 */
public final class MixinAuditEntrypoint implements PreLaunchEntrypoint {

	@Override
	public void onPreLaunch() {
		final long start = System.currentTimeMillis();
		int exitCode = 0;
		try {
			MixinEnvironment.getCurrentEnvironment().audit();
			System.out.println("[mixin-audit] PASSED in " + (System.currentTimeMillis() - start) + " ms");
		} catch (Throwable throwable) {
			System.out.println("[mixin-audit] FAILED");
			throwable.printStackTrace(System.out);
			exitCode = 1;
		}
		System.out.flush();
		Runtime.getRuntime().halt(exitCode);
	}
}
