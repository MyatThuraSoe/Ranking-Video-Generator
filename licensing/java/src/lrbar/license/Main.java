package lrbar.license;

import javax.swing.SwingUtilities;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/** Entry point: opens the GUI, or issues one key when CLI arguments are given. */
public final class Main {

    private Main() {
    }

    public static void main(String[] args) {
        if (args.length > 0) {
            System.exit(runCli(args));
        }
        Theme.install();
        SwingUtilities.invokeLater(() -> {
            LicenseManagerFrame frame = new LicenseManagerFrame();
            frame.setVisible(true);
        });
    }

    // ------------------------------------------------------------------- CLI
    private static int runCli(String[] args) {
        Map<String, String> options = parse(args);
        if (options.containsKey("--help") || options.containsKey("-h")) {
            printHelp();
            return 0;
        }
        String machine = options.getOrDefault("--machine", "");
        if (!MachineId.isValid(machine)) {
            System.err.println("error: --machine must be a 20-character Machine ID "
                    + "(e.g. 7F3A-9C2E-1B44-D07A-55C1).");
            return 2;
        }
        String kind = options.getOrDefault("--type", LicenseIssuer.DAY);
        if (!LicenseIssuer.isKnownType(kind)) {
            System.err.println("error: --type must be 'day' or 'lifetime'.");
            return 2;
        }
        int days = intOption(options, "--days", 1);
        int videos = intOption(options, "--videos", LicenseIssuer.DEFAULT_VIDEOS);
        String note = options.getOrDefault("--note", "");
        String account = options.getOrDefault("--account", "");
        String phone = options.getOrDefault("--phone", "");
        boolean save = !options.containsKey("--no-save");
        boolean quiet = options.containsKey("--quiet");

        try {
            String normalized = MachineId.normalize(machine);
            LicenseIssuer.Issued issued = LicenseIssuer.issue(
                    AppPaths.privateKeyFile(), normalized, kind, days, videos, note);

            boolean savedRecord = true;
            if (save) {
                Record record = new Record();
                record.licenseId = issued.licenseId;
                record.createdAt = Record.nowDisplay();
                record.createdAtEpoch = Instant.now().getEpochSecond();
                record.machineId = normalized;
                record.accountName = account;
                record.phone = phone;
                record.note = note;
                record.type = kind;
                record.issuedAt = issued.issuedAt;
                record.expiresAt = issued.expiresAt;
                record.days = LicenseIssuer.LIFETIME.equals(kind)
                        ? 0 : Math.max(1, days);
                record.videos = issued.videos;
                record.key = issued.key;
                RecordStore history = new RecordStore(AppPaths.recordsFile());
                savedRecord = history.add(record);
                if (!savedRecord) {
                    System.err.println("warning: key issued but the history file "
                            + "could not be saved: " + history.lastError());
                }
            }

            String out = options.get("--out");
            if (out != null && !out.isBlank()) {
                Path path = Paths.get(out);
                Path parent = path.toAbsolutePath().getParent();
                if (parent != null) {
                    Files.createDirectories(parent);
                }
                Files.writeString(path, issued.key + "\n", StandardCharsets.UTF_8);
            }

            if (quiet) {
                System.out.println(issued.key);
                return 0;
            }

            String expiry = LicenseIssuer.LIFETIME.equals(kind)
                    ? "never"
                    : Record.formatEpoch(issued.expiresAt);
            System.out.println("License issued");
            System.out.println("--------------");
            System.out.println("Machine ID  : " + normalized);
            System.out.println("Type        : " + (LicenseIssuer.LIFETIME.equals(kind)
                    ? "Lifetime (never expires, unlimited exports)"
                    : "1-Day (2 video exports by default)"));
            System.out.println("Expires     : " + expiry);
            System.out.println("Video limit : " + (issued.videos == 0
                    ? "Unlimited" : issued.videos));
            System.out.println("License ID  : " + issued.licenseId);
            if (save) {
                System.out.println(savedRecord
                        ? "Saved to    : " + AppPaths.recordsFile()
                        : "Not saved   : history file could not be written");
            }
            System.out.println();
            System.out.println("License key (send this whole line):");
            System.out.println(issued.key);
            return 0;
        } catch (Exception ex) {
            System.err.println("error: " + ex.getMessage());
            return 1;
        }
    }

    private static int intOption(Map<String, String> options, String name,
                                 int fallback) {
        try {
            return Integer.parseInt(options.getOrDefault(name,
                    String.valueOf(fallback)));
        } catch (NumberFormatException ex) {
            return fallback;
        }
    }

    private static Map<String, String> parse(String[] args) {
        Map<String, String> options = new LinkedHashMap<>();
        for (int i = 0; i < args.length; i++) {
            String arg = args[i];
            if (!arg.startsWith("-")) {
                continue;
            }
            if (i + 1 < args.length && !args[i + 1].startsWith("--")) {
                options.put(arg, args[++i]);
            } else {
                options.put(arg, "true");
            }
        }
        return options;
    }

    private static void printHelp() {
        System.out.println("""
                LRBar-RankGen License Manager

                Run without arguments to open the graphical window.

                CLI options:
                  --machine  <ID>     customer Machine ID (required)
                  --type     <kind>   day (default) or lifetime
                  --days     <n>      validity of a day key (default 1)
                  --videos   <n>      export limit of a day key (default 2)
                  --account  <text>   optional account name for the record
                  --phone    <text>   optional phone number for the record
                  --note     <text>   optional note for the record
                  --out      <file>   also write the key to a text file
                  --no-save           do not add a record to the history
                  --quiet             print only the license key
                  --help              show this help
                """);
    }
}
