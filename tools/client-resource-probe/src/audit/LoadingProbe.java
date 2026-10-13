package audit;
import net.fabricmc.api.ClientModInitializer;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.io.*;
import java.security.*;
/** Manual offline probe for the pinned Minecraft 1.20.4 Fabric client. */
public class LoadingProbe implements ClientModInitializer {
  static void digestOnClient(Object mc,Method execute,String phase) throws Exception {
    if(System.getProperty("audit.digestModels")==null)return;
    CompletableFuture<Void> result=new CompletableFuture<>();
    execute.invoke(mc,(Runnable)()->{try{digestModels(mc,phase);result.complete(null);}catch(Throwable e){result.completeExceptionally(e);}});
    result.get(5,TimeUnit.MINUTES);
  }
  /** Optional correctness run; deliberately kept out of the timed reload interval. */
  static void digestModels(Object mc,String phase) throws Exception {
    String mode=System.getProperty("audit.digestModels");
    if(mode==null)return;
    if(!mode.equals("default")&&!mode.equals("all"))throw new IllegalArgumentException("audit.digestModels must be default or all");
    Class<?> registry=Class.forName("net.minecraft.class_2378"),blockType=Class.forName("net.minecraft.class_2248");
    Class<?> modelType=Class.forName("net.minecraft.class_1087"),quadType=Class.forName("net.minecraft.class_777");
    Class<?> stateType=Class.forName("net.minecraft.class_2680"),faceType=Class.forName("net.minecraft.class_2350");
    Class<?> randomType=Class.forName("net.minecraft.class_5819"),idType=Class.forName("net.minecraft.class_1091");
    Method id=registry.getMethod("method_10221",Object.class),toModelId=Class.forName("net.minecraft.class_773").getMethod("method_3340",stateType);
    Method modelGetter=Class.forName("net.minecraft.class_1092").getMethod("method_4742",idType);
    Method getQuads=modelType.getMethod("method_4707",stateType,faceType,randomType),random=randomType.getMethod("method_43049",long.class);
    Method vertices=quadType.getMethod("method_3357"),tint=quadType.getMethod("method_3359"),face=quadType.getMethod("method_3358"),shade=quadType.getMethod("method_24874"),sprite=quadType.getMethod("method_35788");
    Method spriteContents=Class.forName("net.minecraft.class_1058").getMethod("method_45851");
    Method spriteId=Class.forName("net.minecraft.class_7764").getMethod("method_45816");
    Method[] flags={modelType.getMethod("method_4708"),modelType.getMethod("method_4712"),modelType.getMethod("method_24304"),modelType.getMethod("method_4713")};
    List<Object> faces=new ArrayList<>(Arrays.asList(faceType.getEnumConstants()));faces.add(null);
    Object manager=mc.getClass().getMethod("method_1554").invoke(mc);
    List<String> lines=new ArrayList<>(),canonicalLines=new ArrayList<>(),dumpLines=new ArrayList<>();
    Set<String> dumpModels=new HashSet<>();
    for(String selected:System.getProperty("audit.dumpModelQuads","").split(","))if(!selected.isBlank())dumpModels.add(selected.trim());
    if(dumpModels.size()>16)throw new IllegalArgumentException("Select at most 16 model IDs for audit.dumpModelQuads");
    long quadCount=0;int stateCount=0,itemCount=0;
    for(String kind:List.of("blocks","items")) {
      Object values=Class.forName("net.minecraft.class_7923").getField(kind.equals("blocks")?"field_41175":"field_41178").get(null);
      for(Object value:(Iterable<?>)values) {
        String key=id.invoke(values,value).toString();
        Iterable<?> states=Collections.singletonList(null);
        if(kind.equals("blocks")) {
          if(mode.equals("all"))states=(Iterable<?>)Class.forName("net.minecraft.class_2689").getMethod("method_11662").invoke(blockType.getMethod("method_9595").invoke(value));
          else states=List.of(blockType.getMethod("method_9564").invoke(value));
        }
        for(Object state:states) {
          Object modelId=state==null?idType.getConstructor(String.class,String.class,String.class).newInstance(key.substring(0,key.indexOf(':')),key.substring(key.indexOf(':')+1),"inventory"):toModelId.invoke(null,state);
          Object model=modelGetter.invoke(manager,modelId);
          MessageDigest digest=MessageDigest.getInstance("SHA-256");
          MessageDigest canonicalDigest=MessageDigest.getInstance("SHA-256");
          DataOutputStream out=new DataOutputStream(new DigestOutputStream(OutputStream.nullOutputStream(),digest));
          DataOutputStream canonicalOut=new DataOutputStream(new DigestOutputStream(OutputStream.nullOutputStream(),canonicalDigest));
          for(Method flag:flags) {
            boolean flagValue=(Boolean)flag.invoke(model);out.writeBoolean(flagValue);canonicalOut.writeBoolean(flagValue);
          }
          String particle=spriteId.invoke(spriteContents.invoke(modelType.getMethod("method_4711").invoke(model))).toString();
          out.writeUTF(particle);canonicalOut.writeUTF(particle);
          ByteArrayOutputStream quadBuffer=new ByteArrayOutputStream(192);
          DataOutputStream quadOut=new DataOutputStream(quadBuffer);
          boolean dump=dumpModels.contains(modelId.toString());
          // Reset the RNG for each face, as the vanilla block renderer does.
          for(long seed:new long[]{0,1,42,Long.MIN_VALUE})for(Object side:faces) {
            List<?> quads=(List<?>)getQuads.invoke(model,state,side,random.invoke(null,seed));
            out.writeInt(quads.size());canonicalOut.writeInt(quads.size());quadCount+=quads.size();
            List<byte[]> canonicalQuads=new ArrayList<>(quads.size());int quadIndex=0;
            for(Object quad:quads) {
              quadBuffer.reset();
              int[] data=(int[])vertices.invoke(quad);quadOut.writeInt(data.length);
              for(int component:data)quadOut.writeInt(component);
              quadOut.writeInt((Integer)tint.invoke(quad));quadOut.writeUTF(face.invoke(quad).toString());quadOut.writeBoolean((Boolean)shade.invoke(quad));
              quadOut.writeUTF(spriteId.invoke(spriteContents.invoke(sprite.invoke(quad))).toString());
              byte[] encoded=quadBuffer.toByteArray();
              // Ordered output is byte-for-byte the original serialization. Canonicalization only
              // reorders whole records inside this one seed/face group, never vertex or float data.
              out.write(encoded);canonicalQuads.add(encoded);
              if(dump)dumpLines.add(kind+"\t"+modelId+"\t"+seed+"\t"+(side==null?"unculled":side)+"\t"+quadIndex+"\t"+HexFormat.of().formatHex(encoded));
              quadIndex++;
            }
            canonicalQuads.sort(Arrays::compareUnsigned);
            for(byte[] encoded:canonicalQuads)canonicalOut.write(encoded);
          }
          out.close();canonicalOut.close();quadOut.close();
          lines.add(kind+"\t"+modelId+"\t"+HexFormat.of().formatHex(digest.digest()));
          canonicalLines.add(kind+"\t"+modelId+"\t"+HexFormat.of().formatHex(canonicalDigest.digest()));
          if(state==null)itemCount++;else stateCount++;
        }
      }
    }
    Collections.sort(lines);Files.write(Path.of("model-digest-"+phase+".tsv"),lines);
    Collections.sort(canonicalLines);Files.write(Path.of("model-digest-canonical-"+phase+".tsv"),canonicalLines);
    if(!dumpModels.isEmpty())Files.write(Path.of("model-quad-dump-"+phase+".tsv"),dumpLines);
    record("model_digest_"+phase+"\tstates="+stateCount+",items="+itemCount+",quads="+quadCount);
    record("model_digest_canonical_"+phase+"\tstates="+stateCount+",items="+itemCount+",quads="+quadCount);
  }
  static void recordScenaStatistics(String phase) throws Exception {
    if(!Boolean.getBoolean("audit.scenaStatistics"))return;
    final Class<?> cache;
    try {cache=Class.forName("team.minefed.mods.clientcompat.scena.ScenaAbsentLoaderCache");}
    catch(ClassNotFoundException unavailable){record("scena_cache_"+phase+"\tunavailable");return;}
    Object statistics=cache.getMethod("sharedStatistics").invoke(null);
    List<String> fields=new ArrayList<>();
    for(String field:List.of("hits","misses","entries","retainedBytes"))fields.add(field+"="+statistics.getClass().getMethod(field).invoke(statistics));
    record("scena_cache_"+phase+"\t"+String.join(",",fields));
  }
  static Object unwrap(Object model, Class<?> target) throws Exception {
    Class<?> baked=Class.forName("net.minecraft.class_1087");
    for(int i=0;i<16 && !target.isInstance(model);i++) {
      Object next=null;
      for(Class<?> c=model.getClass();c!=null && next==null;c=c.getSuperclass())
        for(Field f:c.getDeclaredFields())if(!Modifier.isStatic(f.getModifiers()) && baked.isAssignableFrom(f.getType())) {
          f.setAccessible(true);Object value=f.get(model);if(value!=null && value!=model){next=value;break;}
        }
      if(next==null)break;
      model=next;
    }
    return model;
  }
  static void verifyShowblock(Object mc) throws Exception {
    Object manager=mc.getClass().getMethod("method_1554").invoke(mc);
    Class<?> modelId=Class.forName("net.minecraft.class_1091");
    Method getModel=Class.forName("net.minecraft.class_1092").getMethod("method_4742",modelId);
    Object blocks=Class.forName("net.minecraft.class_7923").getField("field_41175").get(null);
    Method getId=Class.forName("net.minecraft.class_2378").getMethod("method_10221",Object.class);
    Class<?> wrapper=Class.forName("com.yuushya.modelling.blockentity.showblock.ShowBlockModel");
    Field facing=wrapper.getDeclaredField("facing");facing.setAccessible(true);
    Field backup=wrapper.getDeclaredField("backup");backup.setAccessible(true);
    int count=0;
    String namespace=null;
    for(Object block:(Iterable<?>)blocks) {
      String id=getId.invoke(blocks,block).toString();
      if(!id.endsWith(":showblock"))continue;
      namespace=id.split(":")[0];
      Object definition=Class.forName("net.minecraft.class_2248").getMethod("method_9595").invoke(block);
      for(Object state:(Iterable<?>)Class.forName("net.minecraft.class_2689").getMethod("method_11662").invoke(definition)) {
        Object key=Class.forName("net.minecraft.class_773").getMethod("method_3340",Class.forName("net.minecraft.class_2680")).invoke(null,state);
        Object model=unwrap(getModel.invoke(manager,key),wrapper);
        if(!wrapper.isInstance(model) || !state.toString().contains("facing="+facing.get(model)) || backup.get(model)==null || backup.get(model)==model)
          throw new AssertionError("Incorrect showblock model: "+state+" "+model);
        count++;
      }
    }
    Object item=unwrap(getModel.invoke(manager,modelId.getConstructor(String.class,String.class,String.class).newInstance(namespace,"showblock","inventory")),wrapper);
    if(count!=128 || !wrapper.isInstance(item) || !facing.get(item).toString().equals("south") || backup.get(item)==null || backup.get(item)==item)
      throw new AssertionError("Missing showblock models: "+count);
    Object stone=unwrap(getModel.invoke(manager,modelId.getConstructor(String.class,String.class,String.class).newInstance("minecraft","stone","")),wrapper);
    if(wrapper.isInstance(stone))throw new AssertionError("Wrapped another mod's model");
    record("showblock_models_checked\t"+(count+1));
  }
  static void record(String value) throws Exception {
    Files.writeString(Path.of("probe-results.tsv"), value+"\n", StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    System.out.println("MINEFED_PROBE " + value);
  }
  public void onInitializeClient() {
    Thread worker=new Thread(()->{try {
      Class<?> type=Class.forName("net.minecraft.class_310");
      Object mc=type.getMethod("method_1551").invoke(null);
      Method execute=type.getMethod("execute",Runnable.class);
      long deadline=System.nanoTime()+TimeUnit.MINUTES.toNanos(15);
      boolean reachedTitle=false;
      while(System.nanoTime()<deadline) {
        CompletableFuture<Boolean> ready=new CompletableFuture<>();
        execute.invoke(mc,(Runnable)()->{try {
          Object screen=type.getField("field_1755").get(mc);
          ready.complete(screen!=null && screen.getClass().getName().equals("net.minecraft.class_442") && type.getMethod("method_18506").invoke(mc)==null);
        }catch(Exception e){ready.completeExceptionally(e);}});
        if(ready.get(1,TimeUnit.MINUTES)){reachedTitle=true;break;}
        Thread.sleep(500);
      }
      if(!reachedTitle)throw new TimeoutException("Title screen did not finish loading");
      record("title_ms\t"+java.lang.management.ManagementFactory.getRuntimeMXBean().getUptime());
      recordScenaStatistics("title");
      Class<?> registries=Class.forName("net.minecraft.class_7923");
      verifyShowblock(mc);
      digestOnClient(mc,execute,"title");
      Class<?> registry=Class.forName("net.minecraft.class_2378");
      Method id=registry.getMethod("method_10221",Object.class);
      if (Boolean.getBoolean("audit.dumpRegistries")) for(String kind:List.of("blocks","items")) {
        Object reg=registries.getField(kind.equals("blocks")?"field_41175":"field_41178").get(null);
        List<String> lines=new ArrayList<>();
        for(Object value:(Iterable<?>)reg) {
          lines.add(id.invoke(reg,value).toString());
          if(kind.equals("blocks")) {
            Object states=Class.forName("net.minecraft.class_2248").getMethod("method_9595").invoke(value);
            for(Object state:(Iterable<?>)Class.forName("net.minecraft.class_2689").getMethod("method_11662").invoke(states))lines.add("  "+state);
          }
        }
        Files.write(Path.of("registered-"+kind+".txt"),lines);
      }
      for(int i=0;i<2;i++) {
        Thread.sleep(3000);
        long start=System.nanoTime();
        CompletableFuture<Void> done=new CompletableFuture<>();
        final boolean enablePack=i==0;
        execute.invoke(mc,(Runnable)()->{try {
          String togglePack=System.getProperty("audit.togglePack");
          if(togglePack!=null) {
            Object packs=type.getMethod("method_1520").invoke(mc);
            Class<?> packType=Class.forName("net.minecraft.class_3283");
            packType.getMethod("method_14445").invoke(packs);
            if(!(Boolean)packType.getMethod("method_29207",String.class).invoke(packs,togglePack))
              throw new AssertionError("Missing test pack: "+togglePack);
            Collection<?> current=(Collection<?>)packType.getMethod("method_29210").invoke(packs);
            List<Object> enabled=new ArrayList<>(current);
            if(enablePack) {
              if(enabled.contains(togglePack))throw new AssertionError("Test pack must start disabled");
              enabled.add(togglePack);
            } else if(!enabled.remove(togglePack))throw new AssertionError("Test pack was not applied");
            packType.getMethod("method_14447",Collection.class).invoke(packs,enabled);
          }
          ((CompletableFuture<?>)type.getMethod("method_1521").invoke(mc)).whenComplete((v,e)->{
            if(e!=null){done.completeExceptionally(e);return;}
            try {
              if(togglePack!=null) {
                Object packs=type.getMethod("method_1520").invoke(mc);
                Collection<?> applied=(Collection<?>)Class.forName("net.minecraft.class_3283").getMethod("method_29210").invoke(packs);
                if(applied.contains(togglePack)!=enablePack)
                  throw new AssertionError("Reload reverted the test pack selection");
              }
              done.complete(null);
            }catch(Throwable failure){done.completeExceptionally(failure);}
          });
        }catch(Throwable e){done.completeExceptionally(e);}});
        done.get(10,TimeUnit.MINUTES);
        record("reload_"+i+"_ms\t"+(System.nanoTime()-start)/1000000);
        recordScenaStatistics(enablePack?"apply":"remove");
        if(System.getProperty("audit.togglePack")!=null)record("pack_"+(enablePack?"apply":"remove")+"\ttrue");
        verifyShowblock(mc);
        digestOnClient(mc,execute,enablePack?"apply":"remove");
      }
      record("complete\ttrue");
      if (System.getProperty("audit.jfr") != null)
        for(jdk.jfr.Recording recording:jdk.jfr.FlightRecorder.getFlightRecorder().getRecordings())
          recording.dump(Path.of(System.getProperty("audit.jfr")));
      execute.invoke(mc,(Runnable)()->{try{type.getMethod("method_1490").invoke(mc);}catch(Exception e){throw new RuntimeException(e);}});
    }catch(Throwable e){
      e.printStackTrace();try{record("failed\t"+e);}catch(Exception ignored){}
      try {
        Class<?> type=Class.forName("net.minecraft.class_310");Object mc=type.getMethod("method_1551").invoke(null);
        type.getMethod("execute",Runnable.class).invoke(mc,(Runnable)()->{try{type.getMethod("method_1490").invoke(mc);}catch(Exception failure){failure.printStackTrace();}});
      }catch(Exception failure){failure.printStackTrace();}
    }},"Minefed-loading-probe");
    worker.setDaemon(true);worker.start();
  }
}
