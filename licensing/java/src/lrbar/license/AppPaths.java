package lrbar.license;

import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/** Locates the licensing folder and its files for source runs and the jar. */
public final class AppPaths {

    private AppPaths() {
    }

    private static Path codeSourceDir() {
        try {
            Path location = Paths.get(AppPaths.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI());
            if (Files.isRegularFile(location)) {
                return location.getParent();
            }
            return location;
        } catch (URISyntaxException | RuntimeException ex) {
            return Paths.get(System.getProperty("user.dir"));
        }
    }

    /**
     * The folder containing {@code private_key.pem}. Resolved by walking up from
     * the jar/classes location, so launching the jar by double-click works from
     * any working directory.
     */
    public static Path licensingDir() {
        String override = System.getProperty("lrbar.licensing.dir");
        if (override != null && !override.isBlank()) {
            return Paths.get(override).toAbsolutePath();
        }

        Path start = codeSourceDir();
        Path node = start;
        while (node != null) {
            if (Files.isRegularFile(node.resolve("private_key.pem"))) {
                return node;
            }
            node = node.getParent();
        }

        node = start;
        while (node != null) {
            Path name = node.getFileName();
            if (name != null && "licensing".equals(name.toString())) {
                return node;
            }
            node = node.getParent();
        }

        Path cwd = Paths.get(System.getProperty("user.dir")).toAbsolutePath();
        Path nested = cwd.resolve("licensing");
        if (Files.isRegularFile(nested.resolve("private_key.pem"))) {
            return nested;
        }
        if (Files.isRegularFile(cwd.resolve("private_key.pem"))) {
            return cwd;
        }
        return nested;
    }

    public static Path privateKeyFile() {
        return licensingDir().resolve("private_key.pem");
    }

    public static Path recordsFile() {
        String override = System.getProperty("lrbar.records.file");
        if (override != null && !override.isBlank()) {
            return Paths.get(override).toAbsolutePath();
        }
        return licensingDir().resolve("license_records.json");
    }

    public static void ensureDir(Path file) throws IOException {
        Path parent = file.toAbsolutePath().getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
    }
}
