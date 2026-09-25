package audit;
import net.fabricmc.api.ClientModInitializer;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
/** Manual offline probe for the pinned Minecraft 1.20.4 Fabric client. */
public class LoadingProbe implements ClientModInitializer {
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
        if(!wrapper.isInstance(model) || !state.toString().contains("facing="+facing.get(model)) || backup.get(model)==model)
          throw new AssertionError("Incorrect showblock model: "+state+" "+model);
        count++;
      }
    }
    Object item=unwrap(getModel.invoke(manager,modelId.getConstructor(String.class,String.class,String.class).newInstance(namespace,"showblock","inventory")),wrapper);
    if(count!=128 || !wrapper.isInstance(item) || !facing.get(item).toString().equals("south"))
      throw new AssertionError("Missing showblock models: "+count);
    Object stone=getModel.invoke(manager,modelId.getConstructor(String.class,String.class,String.class).newInstance("minecraft","stone",""));
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
      Class<?> registries=Class.forName("net.minecraft.class_7923");
      verifyShowblock(mc);
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
        execute.invoke(mc,(Runnable)()->{try {
          ((CompletableFuture<?>)type.getMethod("method_1521").invoke(mc)).whenComplete((v,e)->{if(e!=null)done.completeExceptionally(e);else done.complete(null);});
        }catch(Exception e){done.completeExceptionally(e);}});
        done.get(10,TimeUnit.MINUTES);
        record("reload_"+i+"_ms\t"+(System.nanoTime()-start)/1000000);
        verifyShowblock(mc);
      }
      record("complete\ttrue");
      if (System.getProperty("audit.jfr") != null)
        for(jdk.jfr.Recording recording:jdk.jfr.FlightRecorder.getFlightRecorder().getRecordings())
          recording.dump(Path.of(System.getProperty("audit.jfr")));
      execute.invoke(mc,(Runnable)()->{try{type.getMethod("method_1490").invoke(mc);}catch(Exception e){throw new RuntimeException(e);}});
    }catch(Throwable e){e.printStackTrace();try{record("failed\t"+e);}catch(Exception ignored){}}},"Minefed-loading-probe");
    worker.setDaemon(true);worker.start();
  }
}
