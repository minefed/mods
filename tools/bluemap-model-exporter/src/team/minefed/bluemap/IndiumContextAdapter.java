/* Copyright (c) 2026 Minefed. SPDX-License-Identifier: MIT */
package team.minefed.bluemap;

import link.infra.indium.renderer.mesh.MutableQuadViewImpl;
import link.infra.indium.renderer.render.AbstractBlockRenderContext;
import me.jellysquid.mods.sodium.client.model.light.data.LightDataAccess;
import me.jellysquid.mods.sodium.client.render.chunk.terrain.material.Material;
import net.fabricmc.fabric.api.renderer.v1.mesh.QuadEmitter;
import net.fabricmc.fabric.api.renderer.v1.mesh.Mesh;
import net.fabricmc.fabric.api.renderer.v1.render.RenderContext;
import net.minecraft.class_2350;

/** Satisfies Indium's concrete-context optimization while retaining raw, unlit quads. */
public final class IndiumContextAdapter extends AbstractBlockRenderContext {
    private final RenderContext capture;
    public IndiumContextAdapter(RenderContext capture) { this.capture = capture; }
    @Override public QuadEmitter getEmitter() { return capture.getEmitter(); }
    @Override public QuadEmitter getVanillaModelEmitter() { return capture.getEmitter(); }
    @Override public boolean hasTransform() { return capture.hasTransform(); }
    @Override public void pushTransform(QuadTransform transform) { capture.pushTransform(transform); }
    @Override public void popTransform() { capture.popTransform(); }
    @Override public boolean isFaceCulled(class_2350 face) { return false; }
    @Override public BakedModelConsumer bakedModelConsumer() { return capture.bakedModelConsumer(); }
    @Override public java.util.function.Consumer<Mesh> meshConsumer() { return capture.meshConsumer(); }
    @Override protected LightDataAccess getLightCache() {
        throw new IllegalStateException("Offline export must not apply world lighting");
    }
    @Override protected void bufferQuad(MutableQuadViewImpl quad, Material material) {
        throw new IllegalStateException("Offline export must capture before lighting");
    }
}
