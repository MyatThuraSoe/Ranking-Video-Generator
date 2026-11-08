package lrbar.license;

import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Objects;

/** One issued license, as stored in the local history file. */
public final class Record {

    private static final DateTimeFormatter DISPLAY =
            DateTimeFormatter.ofPattern("dd MMM yyyy, HH:mm:ss");

    public String licenseId = "";
    public String createdAt = "";        // local time shown in the history
    public long createdAtEpoch = 0;      // seconds since epoch
    public String machineId = "";
    public String accountName = "";
    public String phone = "";
    public String note = "";
    public String type = "day";          // day | lifetime
    public long issuedAt = 0;
    public long expiresAt = 0;
    public int days = 1;
    public int videos = 2;
    public String key = "";

    public boolean isLifetime() {
        return "lifetime".equals(type);
    }

    public String typeLabel() {
        return isLifetime() ? "Lifetime" : "1-Day";
    }

    public String expiresLabel() {
        if (isLifetime() || expiresAt <= 0) {
            return "Never";
        }
        return formatEpoch(expiresAt);
    }

    public String videosLabel() {
        return isLifetime() ? "Unlimited" : String.valueOf(videos);
    }

    public static String formatEpoch(long epochSeconds) {
        try {
            return Instant.ofEpochSecond(epochSeconds)
                    .atZone(ZoneId.systemDefault())
                    .format(DISPLAY);
        } catch (RuntimeException ex) {
            return "unknown";
        }
    }

    public static String nowDisplay() {
        return Instant.now().atZone(ZoneId.systemDefault()).format(DISPLAY);
    }

    public boolean matches(String query) {
        if (query == null || query.isBlank()) {
            return true;
        }
        String q = query.toLowerCase();
        return contains(accountName, q) || contains(machineId, q)
                || contains(phone, q) || contains(note, q)
                || contains(typeLabel(), q) || contains(licenseId, q)
                || contains(createdAt, q);
    }

    private static boolean contains(String value, String lowerQuery) {
        return value != null && value.toLowerCase().contains(lowerQuery);
    }

    public Record copy() {
        Record r = new Record();
        r.licenseId = licenseId;
        r.createdAt = createdAt;
        r.createdAtEpoch = createdAtEpoch;
        r.machineId = machineId;
        r.accountName = accountName;
        r.phone = phone;
        r.note = note;
        r.type = type;
        r.issuedAt = issuedAt;
        r.expiresAt = expiresAt;
        r.days = days;
        r.videos = videos;
        r.key = key;
        return r;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof Record)) {
            return false;
        }
        Record r = (Record) other;
        return Objects.equals(licenseId, r.licenseId)
                && Objects.equals(key, r.key);
    }

    @Override
    public int hashCode() {
        return Objects.hash(licenseId, key);
    }
}
