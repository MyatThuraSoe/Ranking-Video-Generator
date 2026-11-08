package lrbar.license;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * Local history of every issued license, stored as a JSON array next to the
 * private key ({@code licensing/license_records.json}). Newest record first.
 */
public final class RecordStore {

    private final Path file;
    private final List<Record> records = new ArrayList<>();
    private String lastError = "";

    public RecordStore(Path file) {
        this.file = file;
        load();
    }

    public Path file() {
        return file;
    }

    public synchronized List<Record> all() {
        List<Record> copy = new ArrayList<>(records.size());
        for (Record record : records) {
            copy.add(record.copy());
        }
        return Collections.unmodifiableList(copy);
    }

    public synchronized int size() {
        return records.size();
    }

    /** Empty when the last save succeeded; otherwise the I/O error text. */
    public synchronized String lastError() {
        return lastError;
    }

    public synchronized boolean add(Record record) {
        records.add(0, record.copy());
        return save();
    }

    public synchronized boolean remove(Record record) {
        boolean removed = records.remove(record);
        if (removed) {
            save();
        }
        return removed;
    }

    private void load() {
        if (!Files.isRegularFile(file)) {
            return;
        }
        try {
            String text = Files.readString(file, StandardCharsets.UTF_8).trim();
            if (text.isEmpty()) {
                return;
            }
            Object root = Json.parse(text);
            if (!(root instanceof List<?>)) {
                return;
            }
            for (Object item : (List<?>) root) {
                if (item instanceof Map<?, ?>) {
                    records.add(fromMap((Map<?, ?>) item));
                }
            }
        } catch (IOException | RuntimeException ex) {
            System.err.println("Could not read records: " + ex.getMessage());
        }
    }

    private static Record fromMap(Map<?, ?> map) {
        Record r = new Record();
        r.licenseId = str(map, "licenseId");
        r.createdAt = str(map, "createdAt");
        r.createdAtEpoch = lng(map, "createdAtEpoch");
        r.machineId = str(map, "machineId");
        r.accountName = str(map, "accountName");
        r.phone = str(map, "phone");
        r.note = str(map, "note");
        r.type = str(map, "type").isEmpty() ? "day" : str(map, "type");
        r.issuedAt = lng(map, "issuedAt");
        r.expiresAt = lng(map, "expiresAt");
        r.days = (int) lng(map, "days");
        r.videos = (int) lng(map, "videos");
        r.key = str(map, "key");
        return r;
    }

    private static String str(Map<?, ?> map, String key) {
        Object value = map.get(key);
        return value == null ? "" : String.valueOf(value);
    }

    private static long lng(Map<?, ?> map, String key) {
        Object value = map.get(key);
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException ex) {
            return 0;
        }
    }

    private synchronized boolean save() {
        StringBuilder out = new StringBuilder("[\n");
        for (int i = 0; i < records.size(); i++) {
            Record r = records.get(i);
            out.append("  {\n");
            field(out, "licenseId", r.licenseId, true);
            field(out, "createdAt", r.createdAt, true);
            number(out, "createdAtEpoch", r.createdAtEpoch, true);
            field(out, "machineId", r.machineId, true);
            field(out, "accountName", r.accountName, true);
            field(out, "phone", r.phone, true);
            field(out, "note", r.note, true);
            field(out, "type", r.type, true);
            number(out, "issuedAt", r.issuedAt, true);
            number(out, "expiresAt", r.expiresAt, true);
            number(out, "days", r.days, true);
            number(out, "videos", r.videos, true);
            field(out, "key", r.key, false);
            out.append("  }");
            if (i < records.size() - 1) {
                out.append(',');
            }
            out.append('\n');
        }
        out.append("]\n");

        try {
            AppPaths.ensureDir(file);
            Path tmp = file.resolveSibling(file.getFileName() + ".tmp");
            Files.writeString(tmp, out.toString(), StandardCharsets.UTF_8);
            try {
                Files.move(tmp, file, StandardCopyOption.REPLACE_EXISTING,
                        StandardCopyOption.ATOMIC_MOVE);
            } catch (IOException ex) {
                Files.move(tmp, file, StandardCopyOption.REPLACE_EXISTING);
            }
            lastError = "";
            return true;
        } catch (IOException ex) {
            lastError = ex.getMessage();
            System.err.println("Could not save records: " + ex.getMessage());
            return false;
        }
    }

    private static void field(StringBuilder out, String name, String value,
                              boolean comma) {
        out.append("    ").append(Json.quote(name)).append(": ")
                .append(Json.quote(value));
        out.append(comma ? ",\n" : "\n");
    }

    private static void number(StringBuilder out, String name, long value,
                               boolean comma) {
        out.append("    ").append(Json.quote(name)).append(": ").append(value);
        out.append(comma ? ",\n" : "\n");
    }
}
