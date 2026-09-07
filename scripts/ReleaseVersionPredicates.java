import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import net.fabricmc.loader.api.Version;
import net.fabricmc.loader.api.metadata.version.VersionPredicate;

/** Use Fabric's published predicate API without starting Minecraft or its resolver. */
public final class ReleaseVersionPredicates {
    public static void main(String[] args) throws Exception {
        BufferedReader input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        for (String line; (line = input.readLine()) != null;) {
            String[] fields = line.split("\t", -1);
            if (fields.length != 2) throw new IllegalArgumentException("Expected version and predicate");
            String version = new String(Base64.getDecoder().decode(fields[0]), StandardCharsets.UTF_8);
            String predicate = new String(Base64.getDecoder().decode(fields[1]), StandardCharsets.UTF_8);
            System.out.println(VersionPredicate.parse(predicate).test(Version.parse(version)));
        }
    }
}
