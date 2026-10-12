/* Copyright (c) 2026 Minefed. SPDX-License-Identifier: MIT */
package team.minefed.bluemap;

import net.fabricmc.api.ClientModInitializer;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;

/** Offline, fail-closed capture of Minecraft 1.20.4's final Fabric block quads. */
public final class ModelExporter implements ClientModInitializer {
    private static final String API = "net.fabricmc.fabric.api.renderer.v1.";
    private static final Map<String, Method> METHODS = new ConcurrentHashMap<>();
    private final List<Object> results = new ArrayList<>();
    private final Map<String, String> textures = new LinkedHashMap<>();
    private final Map<String, Object> animatedTextures = new LinkedHashMap<>();
    private final Map<String,Map<String,Object>> opaqueBlocks = new TreeMap<>();
    private Path output;
    private Object client, manager, finder, renderer, material, origin, air;
    private int exportedBlocks, exportedStates;

    static Class<?> type(String name) throws ClassNotFoundException { return Class.forName(name); }
    static Object field(Object instance, String name) throws Exception {
        Class<?> c = instance instanceof Class<?> ? (Class<?>) instance : instance.getClass();
        for (; c != null; c = c.getSuperclass()) try {
            Field f = c.getDeclaredField(name); f.setAccessible(true);
            return f.get(instance instanceof Class<?> ? null : instance);
        } catch (NoSuchFieldException ignored) {}
        throw new NoSuchFieldException(name);
    }
    static Object call(Object target, String name, Object... args) throws Exception {
        Class<?> c = target instanceof Class<?> ? (Class<?>) target : target.getClass();
        String key = c.getName() + "/" + name + Arrays.toString(Arrays.stream(args)
                .map(a -> a == null ? null : a.getClass()).toArray());
        Method chosen = METHODS.get(key);
        if (chosen == null) {
            outer: for (Method m : c.getMethods()) {
                if (!m.getName().equals(name) || m.getParameterCount() != args.length) continue;
                Class<?>[] params = m.getParameterTypes();
                for (int i = 0; i < args.length; i++) {
                    Class<?> p = params[i];
                    if (p.isPrimitive()) p = Map.of(int.class,Integer.class,long.class,Long.class,
                            float.class,Float.class,double.class,Double.class,boolean.class,Boolean.class,
                            byte.class,Byte.class,short.class,Short.class,char.class,Character.class).get(p);
                    if (args[i] == null ? params[i].isPrimitive() : !p.isInstance(args[i])) continue outer;
                }
                chosen = m; chosen.setAccessible(true); METHODS.put(key, chosen); break;
            }
        }
        if (chosen == null) throw new NoSuchMethodException(c.getName() + "." + name);
        try { return chosen.invoke(target instanceof Class<?> ? null : target, args); }
        catch (InvocationTargetException e) {
            if (e.getCause() instanceof Exception x) throw x;
            throw e;
        }
    }
    static Map<String,Object> map(Object... pairs) {
        Map<String,Object> value = new LinkedHashMap<>();
        for (int i=0;i<pairs.length;i+=2) value.put((String)pairs[i], pairs[i+1]);
        return value;
    }
    static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof String s) {
            StringBuilder b = new StringBuilder("\"");
            for(char c:s.toCharArray()) switch(c) {
                case '"' -> b.append("\\\""); case '\\' -> b.append("\\\\");
                case '\n' -> b.append("\\n"); case '\r' -> b.append("\\r"); case '\t' -> b.append("\\t");
                default -> { if(c<32)b.append(String.format("\\u%04x",(int)c)); else b.append(c); }
            }
            return b.append('"').toString();
        }
        if (value instanceof Number n) {
            if (!Double.isFinite(n.doubleValue())) throw new IllegalArgumentException("Non-finite geometry");
            return n.toString();
        }
        if (value instanceof Boolean) return value.toString();
        if (value instanceof Map<?,?> m) return "{" + String.join(",", m.entrySet().stream()
                .map(e -> json(e.getKey().toString()) + ":" + json(e.getValue())).toList()) + "}";
        if (value instanceof Collection<?> c) return "[" + String.join(",",c.stream().map(ModelExporter::json).toList()) + "]";
        throw new IllegalArgumentException("Not JSON: " + value.getClass());
    }
    static String digest(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    private void write(String relative, Object value) throws Exception {
        Path p=output.resolve(relative); Files.createDirectories(p.getParent());
        Files.writeString(p,json(value)+"\n",StandardCharsets.UTF_8);
    }
    private String sprite(Object sprite) throws Exception {
        Object contents=call(sprite,"method_45851");
        String id=field(contents,"field_40536").toString();
        if(id.contains("missingno")) throw new IllegalStateException("Missing sprite: "+id);
        if(textures.containsKey(id)) return textures.get(id);
        Object image=field(contents,"field_40539");
        int width=(int)field(contents,"field_40537"),height=(int)field(contents,"field_40538");
        int imageWidth=(int)call(image,"method_4307"),imageHeight=(int)call(image,"method_4323");
        Object animation=field(contents,"field_40541");
        if((imageWidth!=width||imageHeight!=height)&&
                (animation==null||imageWidth!=width||width!=height||imageHeight%height!=0))
            throw new IllegalStateException("Animation is not a square-frame vertical strip: "+id);
        String exported="minefed_bluemap:exported/"+id.replace(':','/');
        if(!exported.matches("[a-z0-9_.-]+:[a-z0-9_./-]+") || exported.contains(".."))
            throw new IllegalArgumentException("Invalid sprite ID: "+id);
        Path p=output.resolve("assets/minefed_bluemap/textures/"+exported.split(":",2)[1]+".png");
        Files.createDirectories(p.getParent()); call(image,"method_4314",p);
        if(animation!=null) {
            if(imageWidth!=width||width!=height||imageHeight%height!=0)
                throw new IllegalStateException("BlueMap requires square-frame vertical animation: "+id);
            List<Object> frames=new ArrayList<>();
            for(Object frame:(List<?>)field(animation,"field_28472"))
                frames.add(map("index",field(frame,"field_28475"),"time",field(frame,"field_28476")));
            write(output.relativize(p).toString()+".mcmeta",map("animation",map("frames",frames,
                    "interpolate",field(animation,"field_40542"))));
            animatedTextures.put(id,map("frames",imageHeight/height));
        }
        textures.put(id,exported); return exported;
    }

    /** Captures the emitter after the model's complete transform stack. */
    private final class Capture implements InvocationHandler {
        final Object state,delegate,emitter,context,world;
        final List<Object> quads=new ArrayList<>(),transforms=new ArrayList<>();
        final Set<String> dependencies=new TreeSet<>();
        final long seed;
        boolean ambientOcclusion;
        Capture(Object state,long seed) throws Exception {
            this.state=state; this.seed=seed;
            delegate=call(call(renderer,"meshBuilder"),"getEmitter");
            emitter=Proxy.newProxyInstance(getClass().getClassLoader(),new Class<?>[]{type(API+"mesh.QuadEmitter")},this::emit);
            Object proxy=Proxy.newProxyInstance(getClass().getClassLoader(),new Class<?>[]{type(API+"render.RenderContext")},this);
            Object compatible=proxy;
            try {
                type("link.infra.indium.renderer.render.AbstractBlockRenderContext");
                compatible=type("team.minefed.bluemap.IndiumContextAdapter")
                        .getConstructor(type(API+"render.RenderContext")).newInstance(proxy);
            }catch(ClassNotFoundException ignored) {}
            context=compatible;
            List<Class<?>> views=new ArrayList<>(List.of(type("net.minecraft.class_1920")));
            try { views.add(type("net.fabricmc.fabric.api.rendering.data.v1.RenderAttachedBlockView")); }
            catch(ClassNotFoundException ignored) {}
            world=Proxy.newProxyInstance(getClass().getClassLoader(),views.toArray(Class<?>[]::new),this::world);
        }
        Object random() { try { return call(type("net.minecraft.class_5819"),"method_43049",seed); }
            catch(Exception e){throw new RuntimeException(e);} }
        private Object objectMethod(Object proxy,Method method,Object[] args) {
            return switch(method.getName()) {
                case "toString" -> "MinefedOfflineExportContext";
                case "hashCode" -> System.identityHashCode(proxy);
                case "equals" -> proxy==args[0];
                default -> throw new UnsupportedOperationException(method.toString());
            };
        }
        private Object world(Object proxy,Method method,Object[] args) throws Throwable {
            if(method.getDeclaringClass()==Object.class)return objectMethod(proxy,method,args);
            switch(method.getName()) {
                case "method_8320": // BlockView.getBlockState
                    if(origin.equals(args[0]))return state;
                    dependencies.add("neighbor:"+args[0]); return air;
                case "method_8316": // BlockView.getFluidState
                    if(origin.equals(args[0]))return call(state,"method_26227");
                    dependencies.add("fluid:"+args[0]); return call(air,"method_26227");
                case "method_8321", "getBlockEntityRenderAttachment":
                    dependencies.add("block-entity:"+args[0]); return null;
                case "method_23752": dependencies.add("biome-color"); return 0xffffff;
                case "method_24852": dependencies.add("directional-light:"+Arrays.toString(args)); return 1f;
                case "method_8314", "method_22335": dependencies.add("light:"+Arrays.toString(args)); return 15;
                case "method_31607": return 384;
                case "method_31608": return -64;
                default:
                    if(method.isDefault())return InvocationHandler.invokeDefault(proxy,method,args==null?new Object[0]:args);
                    throw new UnsupportedOperationException("World query: "+method);
            }
        }
        private void vanilla(Object model,Object state) throws Exception {
            List<Object> sides=new ArrayList<>(Arrays.asList(type("net.minecraft.class_2350").getEnumConstants()));
            sides.add(null);
            for(Object side:sides) for(Object q:(List<?>)call(model,"method_4707",state,side,random())) {
                call(emitter,"fromVanilla",q,material,side); call(emitter,"emit");
            }
        }
        @Override public Object invoke(Object proxy,Method method,Object[] args) throws Throwable {
            if(method.getDeclaringClass()==Object.class)return objectMethod(proxy,method,args);
            switch(method.getName()) {
                case "getEmitter": return emitter;
                case "hasTransform": return !transforms.isEmpty();
                case "pushTransform": transforms.add(args[0]); return null;
                case "popTransform": transforms.remove(transforms.size()-1); return null;
                case "isFaceCulled": return false;
                case "bakedModelConsumer": return Proxy.newProxyInstance(getClass().getClassLoader(),
                        new Class<?>[]{type(API+"render.RenderContext$BakedModelConsumer")},(p,m,a)->{
                            if(m.getName().equals("accept")){vanilla(a[0],a.length==2?a[1]:state);return null;}
                            if(m.isDefault())return InvocationHandler.invokeDefault(p,m,a);
                            return objectMethod(p,m,a);
                        });
                default:
                    if(method.isDefault())return InvocationHandler.invokeDefault(proxy,method,args==null?new Object[0]:args);
                    throw new UnsupportedOperationException("Render context: "+method);
            }
        }
        private Object emit(Object proxy,Method method,Object[] args) throws Throwable {
            if(method.getDeclaringClass()==Object.class)return objectMethod(proxy,method,args);
            if(method.getName().equals("emit")) {
                boolean keep=true;
                for(int i=transforms.size()-1;i>=0;i--)if(!(boolean)call(transforms.get(i),"transform",delegate)){keep=false;break;}
                if(keep)recordQuad();
                call(delegate,"emit"); return emitter;
            }
            Object value=method.invoke(delegate,args);
            return value==delegate?emitter:value;
        }
        private void recordQuad() throws Exception {
            int color=(int)call(delegate,"color",0);
            for(int i=1;i<4;i++) if((int)call(delegate,"color",i)!=color)
                throw new IllegalStateException("Per-vertex colors cannot be represented by BlueMap 5.3");
            if((color>>>24)!=255)throw new IllegalStateException("Vertex opacity cannot be represented by BlueMap 5.3");
            Object sprite=call(finder,"find",delegate);
            float minU=(float)call(sprite,"method_4594"), maxU=(float)call(sprite,"method_4577");
            float minV=(float)call(sprite,"method_4593"), maxV=(float)call(sprite,"method_4575");
            List<Object> positions=new ArrayList<>(),uv=new ArrayList<>();
            for(int i=0;i<4;i++) {
                positions.add(List.of((float)call(delegate,"x",i)*16,(float)call(delegate,"y",i)*16,(float)call(delegate,"z",i)*16));
                uv.add(List.of(((float)call(delegate,"u",i)-minU)/(maxU-minU)*16,
                        ((float)call(delegate,"v",i)-minV)/(maxV-minV)*16));
            }
            Object mat=call(delegate,"material"),face=call(delegate,"cullFace");
            if((boolean)call(mat,"emissive"))throw new IllegalStateException("Emissive material needs BlueMap light semantics");
            String quadAo=call(mat,"ambientOcclusion").toString();
            if(!quadAo.equals("DEFAULT")&&Boolean.parseBoolean(quadAo)!=ambientOcclusion)
                throw new IllegalStateException("Per-quad ambient occlusion differs from model");
            Map<String,Object> q=map("positions",positions,"uv",uv,"texture",sprite(sprite),
                    "direction",call(call(delegate,"lightFace"),"method_10151"),
                    "tintindex",(boolean)call(mat,"disableColorIndex")?-1:call(delegate,"colorIndex"),
                    "color",String.format("#%06x",color&0xffffff),"shade",!(boolean)call(mat,"disableDiffuse"));
            if(face!=null)q.put("cullface",call(face,"method_10151"));
            quads.add(q);
        }
        Map<String,Object> capture(Object model) throws Exception { return capture(model,false); }
        Map<String,Object> capture(Object model,boolean allowEmpty) throws Exception {
            ambientOcclusion=(boolean)call(model,"method_4708");
            try { call(model,"emitBlockQuads",world,state,origin,(Supplier<Object>)this::random,context); }
            catch(Exception error) {
                // Continuity normally resets its thread-local transform after emission,
                // but not in a finally block. A rejected quad must not poison later states.
                try { ((ThreadLocal<?>)field(type("me.pepperbell.continuity.client.model.ModelObjectsContainer"),"THREAD_LOCAL")).remove(); }
                catch(ClassNotFoundException ignored) {}
                catch(Exception cleanup) { error.addSuppressed(cleanup); }
                throw error;
            }
            if(!transforms.isEmpty())throw new IllegalStateException("Model leaked quad transforms");
            if(!dependencies.isEmpty()&&!System.getProperty("minefed.bluemap.contextual","reject").equals("isolated"))
                throw new IllegalStateException("Context-dependent model: "+dependencies);
            if(quads.isEmpty()&&!allowEmpty)throw new IllegalStateException("Empty/builtin model requires a separate renderer");
            Map<String,Object> result=map("ambientocclusion",ambientOcclusion,"bluemap_quads",quads);
            if(quads.isEmpty())result.put("minefed_export_empty",true);
            if(!dependencies.isEmpty())result.put("minefed_export_context",map("mode","isolated","queries",dependencies));
            return result;
        }
    }
    private static String properties(Object state) {
        String description=state.toString(); int start=description.indexOf('[');
        return start<0?"":description.substring(start+1,description.length()-1);
    }
    private Object model(Object state) throws Exception {
        Object key=call(type("net.minecraft.class_773"),"method_3340",state);
        Object model=call(manager,"method_4742",key);
        if(model==call(manager,"method_4744"))throw new IllegalStateException("Minecraft missing baked model");
        return model;
    }
    private String saveModel(Map<String,Object> data) throws Exception {
        String hash=digest(json(data).getBytes(StandardCharsets.UTF_8));
        String path="assets/minefed_bluemap/models/block/"+hash+".json";
        if(!Files.exists(output.resolve(path)))write(path,data);
        return "minefed_bluemap:block/"+hash;
    }
    private Object multipart(Object model) throws Exception {
        Set<Object> visited=Collections.newSetFromMap(new IdentityHashMap<>());
        Class<?> baked=type("net.minecraft.class_1087");
        while(model!=null&&visited.add(model)) {
            if(model.getClass()==type("net.minecraft.class_1095"))return model;
            Object child=null;
            for(Class<?> c=model.getClass();c!=null;c=c.getSuperclass())for(Field f:c.getDeclaredFields()) {
                if(Modifier.isStatic(f.getModifiers())||!baked.isAssignableFrom(f.getType()))continue;
                f.setAccessible(true); Object candidate=f.get(model);
                if(candidate!=null) {
                    if(child!=null&&child!=candidate)return null;
                    child=candidate;
                }
            }
            model=child;
        }
        return null;
    }
    private static List<String> canonicalQuads(Collection<?> quads) {
        return quads.stream().map(ModelExporter::json).sorted().toList();
    }
    @SuppressWarnings("unchecked")
    private boolean intentionallyEmptyMultipart(Object root,Object state) throws Exception {
        Object multi=multipart(root);
        if(multi==null)return false;
        List<?> selectors=(List<?>)field(multi,"field_5427");
        if(selectors.isEmpty())return false;
        for(Object selector:selectors)
            if(((Predicate<Object>)call(selector,"getLeft")).test(state))return false;
        return true;
    }
    private Object immutableSegment(Object model) throws Exception {
        Set<Object> visited=Collections.newSetFromMap(new IdentityHashMap<>());
        Class<?> baked=type("net.minecraft.class_1087");
        while(model!=null&&visited.add(model)) {
            String kind=model.getClass().getName();
            if(kind.endsWith(".MultipartSegmentBakedModelFabric")||kind.equals("net.minecraft.class_1093"))return model;
            Object child=null;
            for(Class<?> c=model.getClass();c!=null;c=c.getSuperclass())for(Field f:c.getDeclaredFields()) {
                if(Modifier.isStatic(f.getModifiers())||!baked.isAssignableFrom(f.getType()))continue;
                f.setAccessible(true);Object candidate=f.get(model);
                if(candidate!=null) {
                    if(child!=null&&child!=candidate)return null;
                    child=candidate;
                }
            }
            model=child;
        }
        return null;
    }
    /** Preserve runtime-translated Diagonal selectors without expanding every geometry combination. */
    @SuppressWarnings("unchecked")
    private boolean exportMultipart(String id,List<?> states) throws Exception {
        if(!id.startsWith("diagonal"))return false;
        Object root=model(states.get(0)),multi=multipart(root);
        if(multi==null)return false;
        List<?> pairs=(List<?>)field(multi,"field_5427");
        if(pairs.isEmpty())throw new IllegalStateException("Multipart model has no selectors");
        List<String> descriptions=states.stream().map(ModelExporter::properties).toList();
        MultipartConditions.Converter converter=MultipartConditions.prepare(descriptions);
        Map<String,SortedSet<String>> propertyValues=new TreeMap<>();
        for(String description:descriptions)if(!description.isEmpty())for(String entry:description.split(",")) {
            String[] pair=entry.split("=",2);
            propertyValues.computeIfAbsent(pair[0],ignored->new TreeSet<>()).add(pair[1]);
        }
        List<Object> parts=new ArrayList<>(); List<Integer> matchedCounts=new ArrayList<>();
        List<BitSet> matches=new ArrayList<>(); List<Map<String,Object>> models=new ArrayList<>();
        Set<Integer> probes=new TreeSet<>(); BitSet covered=new BitSet(states.size());
        boolean exhaustiveGeometry=root!=multi;
        for(int i=0;i<Math.min(16,states.size());i++)probes.add(i*(states.size()-1)/Math.max(1,Math.min(16,states.size())-1));
        // An unknown wrapper can change only a rare state; sample checks are not
        // sufficient to strip it. Keep the compact output but validate every state.
        if(root!=multi)for(int i=0;i<states.size();i++)probes.add(i);
        for(Object pair:pairs) {
            Predicate<Object> predicate=(Predicate<Object>)call(pair,"getLeft");
            Object part=call(pair,"getRight");
            BitSet matching=new BitSet(states.size());
            for(int i=0;i<states.size();i++)if(predicate.test(states.get(i)))matching.set(i);
            if(matching.isEmpty())continue;
            // These final Diagonal segment classes return a fixed quadMap, independent of state/random.
            // Refuse unknown components rather than inferring this from only a few captures.
            String kind=part.getClass().getName();
            Object immutable=immutableSegment(part);
            if(immutable==null)
                throw new IllegalStateException("Unsupported multipart component: "+kind);
            // Keep actual wrapped emissions. Any wrapper, including Continuity CTM,
            // requires the complete state/seed union check below, not a class allowlist.
            exhaustiveGeometry|=part!=immutable;
            int first=matching.nextSetBit(0),last=matching.length()-1;
            Map<String,Object> data=new Capture(states.get(first),42).capture(part);
            Map<String,Object> check=new Capture(states.get(last),987654321).capture(part);
            if(!json(data).equals(json(check))||data.containsKey("minefed_export_context"))
                throw new IllegalStateException("Multipart component depends on random/state/context: "+kind);
            data.put("ambientocclusion",call(root,"method_4708"));
            probes.add(first); probes.add(last); covered.or(matching);
            matches.add(matching); models.add(data); matchedCounts.add(matching.cardinality());
            Map<String,Object> condition=converter.condition(matching);
            parts.add(map("when",condition,"apply",map("model",saveModel(data),"x",0,"y",0,"uvlock",false)));
        }
        // Every state must point to the same multipart graph. Wrappers may decorate it;
        // compare their final emitted quads with the selected component union at probes.
        if(exhaustiveGeometry)for(int i=0;i<states.size();i++)probes.add(i);
        for(int i=0;i<states.size();i++) {
            Object stateModel=model(states.get(i));
            if(multipart(stateModel)!=multi)throw new IllegalStateException("Multipart graph differs across states");
            if(stateModel!=multi)probes.add(i);
        }
        int empty=covered.nextClearBit(0);if(empty<states.size())probes.add(empty);
        for(int index:probes) {
            List<Object> expected=new ArrayList<>();
            for(int component=0;component<matches.size();component++)if(matches.get(component).get(index))
                expected.addAll((List<Object>)models.get(component).get("bluemap_quads"));
            Map<String,Object> actual=new Capture(states.get(index),42).capture(model(states.get(index)),expected.isEmpty());
            if(actual.containsKey("minefed_export_context")||!canonicalQuads(expected).equals(canonicalQuads((List<?>)actual.get("bluemap_quads"))))
                throw new IllegalStateException("Multipart wrapper changes component geometry: "+descriptions.get(index));
            if(!actual.get("ambientocclusion").equals(call(root,"method_4708")))
                throw new IllegalStateException("Multipart wrapper changes ambient occlusion across states");
            if((exhaustiveGeometry||model(states.get(index))!=multi)&&!json(actual).equals(json(new Capture(states.get(index),987654321)
                    .capture(model(states.get(index)),expected.isEmpty()))))
                throw new IllegalStateException("Multipart wrapper changes geometry with random seed");
        }
        if(parts.isEmpty())throw new IllegalStateException("No multipart components apply");
        String[] path=id.split(":",2);
        write("assets/"+path[0]+"/blockstates/"+path[1]+".json",map("multipart",parts));
        exportedBlocks++;exportedStates+=states.size();
        results.add(map("block",id,"states",states.size(),"exported",true,"format","multipart",
                "components",parts.size(),"propertyValues",propertyValues,"matchedStateCounts",matchedCounts,
                "emptyStates",states.size()-covered.cardinality(),"geometryProbes",probes.size(),
                "rootModelClass",root.getClass().getName(),"multipartModelClass",multi.getClass().getName(),
                "isolatedContextStates",0,"failures",List.of()));
        write("export-report.json",report(false));
        System.out.println("MINEFED_BLUEMAP_EXPORT "+id+" states="+states.size()+" multipart="+parts.size()+" exported=true failures=0");
        return true;
    }
    private void exportBlock(String id,Object block) throws Exception {
        Map<String,Object> variants=new LinkedHashMap<>();
        List<Object> failures=new ArrayList<>(); int count=0,contextual=0; boolean allOpaque=true;
        List<?> states=(List<?>)call(call(block,"method_9595"),"method_11662");
        int max=Integer.getInteger("minefed.bluemap.maxStates",65536);
        if(states.size()<=max)try { if(exportMultipart(id,states))return; }
        catch(Exception error) {
            System.err.println("MINEFED_BLUEMAP_EXPORT multipart fallback "+id+": "+error);
        }
        for(Object state:states) {
            String properties=properties(state);
            count++;
            if(count>max){failures.add(map("state",properties,"error","State limit exceeded"));break;}
            try {
                Object model=model(state);
                Capture primary=new Capture(state,42);
                boolean allowEmpty=id.startsWith("diagonal")&&intentionallyEmptyMultipart(model,state);
                Map<String,Object> data=primary.capture(model,allowEmpty);
                // A state-only export must not silently freeze random-weighted model selection.
                if(!json(data).equals(json(new Capture(state,987654321).capture(model,allowEmpty))))
                    throw new IllegalStateException("Random-dependent model requires weighted model export");
                if(data.containsKey("minefed_export_context"))contextual++;
                // Only mark a whole block opaque after every registered state passes
                // Minecraft's opaque-full-culling-shape check without world queries.
                allOpaque&=!data.containsKey("minefed_export_context")&&
                        (boolean)call(state,"method_26216",primary.world,origin)&&primary.dependencies.isEmpty();
                String modelId=saveModel(data);
                variants.put(properties,map("model",modelId,"x",0,"y",0,"uvlock",false));
            }catch(Exception error) {
                Throwable cause=error;while(cause.getCause()!=null)cause=cause.getCause();
                failures.add(map("state",properties,"error",cause.toString()));
            }
        }
        boolean complete=failures.isEmpty()&&!variants.isEmpty();
        if(complete) {
            String[] parts=id.split(":",2);
            write("assets/"+parts[0]+"/blockstates/"+parts[1]+".json",map("variants",variants));
            if(allOpaque) {
                Map<String,Object> properties=opaqueBlocks.computeIfAbsent(parts[0],ignored->new TreeMap<>());
                properties.put(id,map("culling",true,"occluding",true));
                write("assets/"+parts[0]+"/blockProperties.json",properties);
            }
            exportedBlocks++; exportedStates+=count;
        }
        results.add(map("block",id,"states",count,"exported",complete,"opaqueFullCube",complete&&allOpaque,
                "isolatedContextStates",contextual,"failures",failures));
        write("export-report.json",report(false));
        System.out.println("MINEFED_BLUEMAP_EXPORT "+id+" states="+count+" exported="+complete+" failures="+failures.size());
    }
    private Map<String,Object> report(boolean complete) {
        return map("schemaVersion",1,"minecraft","1.20.4","complete",complete,"distribution","local-only",
                "exportedBlocks",exportedBlocks,"exportedStates",exportedStates,"textures",textures,
                "animatedTextures",animatedTextures,
                "contextualMode",System.getProperty("minefed.bluemap.contextual","reject"),
                "limits",List.of("State-only geometry; context-dependent models require an explicit isolated snapshot option. Its connected placements can differ from the game.",
                    "Random-dependent, emissive and per-vertex color models are rejected. Animated textures require square-frame vertical strips.",
                    "Two seeds detect common weighted models but do not prove invariance over every seed.",
                    "Block entities and entity renderers are not exported. No generated assets have been licensed for public redistribution by this tool."),
                "blocks",results);
    }
    private void export() throws Exception {
        if(!Boolean.getBoolean("minefed.bluemap.disposable"))throw new IllegalStateException("Set minefed.bluemap.disposable=true only in a new offline fixture");
        if(field(client,"field_1687")!=null)throw new IllegalStateException("Export must run at title screen without any loaded world");
        output=Path.of(System.getProperty("minefed.bluemap.output","build/bluemap-export")).toAbsolutePath().normalize();
        if(Files.exists(output))throw new IllegalStateException("Use a fresh output directory: "+output);
        Files.createDirectories(output);
        manager=call(client,"method_1554");
        Object atlas=call(manager,"method_24153",type("net.minecraft.class_2960").getConstructor(String.class).newInstance("minecraft:textures/atlas/blocks.png"));
        finder=call(type(API+"model.SpriteFinder"),"get",atlas);
        renderer=call(field(type(API+"RendererAccess"),"INSTANCE"),"getRenderer");
        if(renderer==null)throw new IllegalStateException("Fabric renderer unavailable; use Indigo or Sodium + Indium");
        material=call(call(renderer,"materialFinder"),"find");
        origin=field(type("net.minecraft.class_2338"),"field_10980");
        Object registry=field(type("net.minecraft.class_7923"),"field_41175");
        Object stone=null;
        for(Object block:(Iterable<?>)registry) {
            String id=call(registry,"method_10221",block).toString();
            if(id.equals("minecraft:air"))air=call(block,"method_9564");
            if(id.equals("minecraft:stone"))stone=call(block,"method_9564");
        }
        if(air==null||stone==null)throw new IllegalStateException("Vanilla registry probe missing");
        Object stoneKey=call(type("net.minecraft.class_773"),"method_3340",stone);
        Map<String,Object> probe=new Capture(stone,42).capture(call(manager,"method_4742",stoneKey));
        if(((List<?>)probe.get("bluemap_quads")).size()!=6)throw new IllegalStateException("Stone quad capture failed");
        System.out.println("MINEFED_BLUEMAP_EXPORT capture-probe=passed");
        Set<String> namespaces=new HashSet<>(Arrays.asList(System.getProperty("minefed.bluemap.namespaces","pfm,diagonalfences,diagonalwalls,diagonalwindows").split(",")));
        Set<String> ids=new HashSet<>(Arrays.asList(System.getProperty("minefed.bluemap.blocks","").split(",")));
        write("pack.mcmeta",map("pack",map("pack_format",22,"description","Minefed local baked-model export for BlueMap")));
        SortedMap<String,Object> selected=new TreeMap<>(Comparator.<String,Boolean>comparing(id->!id.startsWith("pfm:")).thenComparing(Comparator.naturalOrder()));
        for(Object block:(Iterable<?>)registry) {
            String id=call(registry,"method_10221",block).toString();
            if(ids.contains(id)||(ids.contains("")&&namespaces.contains(id.split(":",2)[0])))selected.put(id,block);
        }
        for(Map.Entry<String,Object> entry:selected.entrySet())exportBlock(entry.getKey(),entry.getValue());
        if(results.isEmpty())throw new IllegalStateException("No registered block matched the export selection");
        write("export-report.json",report(true));
        Files.writeString(output.resolve("LOCAL-ONLY.txt"),"Generated from the installed client's third-party assets. Do not commit or publish this directory without the applicable asset license review.\n");
    }
    @Override public void onInitializeClient() {
        new Thread(()->{
            try {
                client=call(type("net.minecraft.class_310"),"method_1551");
                long deadline=System.nanoTime()+TimeUnit.MINUTES.toNanos(20);
                while(System.nanoTime()<deadline) {
                    CompletableFuture<Boolean> ready=new CompletableFuture<>();
                    call(client,"execute",(Runnable)()->{try {
                        Object screen=field(client,"field_1755");
                        ready.complete(screen!=null&&screen.getClass().getName().equals("net.minecraft.class_442")&&call(client,"method_18506")==null);
                    }catch(Exception e){ready.completeExceptionally(e);}});
                    if(ready.get(1,TimeUnit.MINUTES))break;
                    Thread.sleep(500);
                }
                if(System.nanoTime()>=deadline)throw new TimeoutException("Title screen timed out");
                CompletableFuture<Void> done=new CompletableFuture<>();
                call(client,"execute",(Runnable)()->{try{export();done.complete(null);}catch(Exception e){done.completeExceptionally(e);}});
                done.get(60,TimeUnit.MINUTES);
                System.out.println("MINEFED_BLUEMAP_EXPORT complete blocks="+exportedBlocks+" states="+exportedStates);
                call(client,"execute",(Runnable)()->{try{call(client,"method_1490");}catch(Exception e){throw new RuntimeException(e);}});
            }catch(Throwable e){
                e.printStackTrace();System.err.println("MINEFED_BLUEMAP_EXPORT failed "+e);
                if(client!=null&&Boolean.getBoolean("minefed.bluemap.disposable"))try {
                    call(client,"execute",(Runnable)()->{try{call(client,"method_1490");}catch(Exception ignored){}});
                }catch(Exception ignored){}
            }
        },"Minefed-BlueMap-export").start();
    }
}
