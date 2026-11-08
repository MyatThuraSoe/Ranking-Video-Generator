package lrbar.license;

import javax.swing.JLabel;
import javax.swing.JRadioButton;
import javax.swing.JTable;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SwingUtilities;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Drives the real Swing window without showing it: fills the form, generates a
 * key, checks the history table and the search filter. Run with
 * {@code java -cp build\classes lrbar.license.GuiSmokeTest} after building.
 */
public final class GuiSmokeTest {

    private GuiSmokeTest() {
    }

    public static void main(String[] args) throws Exception {
        Path dir = Files.createTempDirectory("lrbar-java-gui-");
        System.setProperty("lrbar.records.file", dir.resolve("records.json").toString());

        Theme.install();
        AtomicReference<LicenseManagerFrame> reference = new AtomicReference<>();
        SwingUtilities.invokeAndWait(() -> reference.set(new LicenseManagerFrame()));
        LicenseManagerFrame frame = reference.get();

        SwingUtilities.invokeAndWait(() -> {
            field(frame, "machineField", JTextField.class)
                    .setText("e09f18a54b04478f6b8f");
            field(frame, "accountField", JTextField.class)
                    .setText("Rahim Traders");
            field(frame, "phoneField", JTextField.class)
                    .setText("+8801712345678");
            field(frame, "noteArea", JTextArea.class)
                    .setText("Java GUI smoke test");
            field(frame, "dayRadio", JRadioButton.class).setSelected(true);
            invoke(frame, "updateTypeControls");
            invoke(frame, "generateKey");
        });

        String key = text(frame, "resultArea", JTextArea.class);
        check(key.startsWith("LRBG1.") && key.split("\\.").length == 3,
                "generated key shape");
        check(key.length() > 200, "generated key length");

        RecordStore store = value(frame, "store", RecordStore.class);
        check(store.size() == 1, "one record saved");
        check("Rahim Traders".equals(store.all().get(0).accountName),
                "account name saved");
        check("E09F-18A5-4B04-478F-6B8F".equals(store.all().get(0).machineId),
                "machine ID normalized");
        check(store.all().get(0).videos == 2, "day key video limit");

        JTable table = field(frame, "table", JTable.class);
        check(table.getRowCount() == 1, "history table shows the record");

        SwingUtilities.invokeAndWait(() ->
                field(frame, "searchField", JTextField.class).setText("rahim"));
        check(table.getRowCount() == 1, "search finds by account");

        SwingUtilities.invokeAndWait(() ->
                field(frame, "searchField", JTextField.class).setText("zzz-no-match"));
        check(table.getRowCount() == 0, "search hides non-matches");

        SwingUtilities.invokeAndWait(() ->
                field(frame, "searchField", JTextField.class).setText(""));
        check(table.getRowCount() == 1, "clearing search restores rows");

        JLabel status = field(frame, "statusLabel", JLabel.class);
        check(status.getText().contains("saved to history"), "success status");

        // A second, lifetime key must store its own row and show "Lifetime".
        SwingUtilities.invokeAndWait(() -> {
            field(frame, "lifetimeRadio", JRadioButton.class).setSelected(true);
            invoke(frame, "updateTypeControls");
            invoke(frame, "generateKey");
        });
        check(store.size() == 2, "second record saved");
        check(store.all().get(0).isLifetime(), "lifetime record first");
        check(table.getRowCount() == 2, "history table updated");

        // The key output must stay readable, not squeezed to a few pixels.
        SwingUtilities.invokeAndWait(() -> {
            frame.addNotify();
            frame.validate();
        });
        JTextArea result = field(frame, "resultArea", JTextArea.class);
        check(result.getParent().getHeight() >= 70,
                "key area usable at default size (" + result.getParent().getHeight() + "px)");
        SwingUtilities.invokeAndWait(() -> {
            frame.setSize(frame.getMinimumSize());
            frame.validate();
        });
        check(result.getParent().getHeight() >= 70,
                "key area usable at minimum size (" + result.getParent().getHeight() + "px)");

        SwingUtilities.invokeAndWait(frame::dispose);
        System.out.println("GUI SMOKE OK  (key " + key.substring(0, 24) + "...)");
    }

    private static void check(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError("FAILED: " + label);
        }
        System.out.println("  ok  " + label);
    }

    private static String text(Object target, String name, Class<?> type) {
        try {
            return ((JTextArea) field(target, name, type)).getText();
        } catch (RuntimeException ex) {
            throw new AssertionError("cannot read " + name, ex);
        }
    }

    @SuppressWarnings("unchecked")
    private static <T> T field(Object target, String name, Class<T> type) {
        try {
            Field field = target.getClass().getDeclaredField(name);
            field.setAccessible(true);
            return (T) field.get(target);
        } catch (ReflectiveOperationException ex) {
            throw new AssertionError("cannot access " + name, ex);
        }
    }

    @SuppressWarnings("unchecked")
    private static <T> T value(Object target, String name, Class<T> type) {
        return field(target, name, type);
    }

    private static void invoke(Object target, String name) {
        try {
            Method method = target.getClass().getDeclaredMethod(name);
            method.setAccessible(true);
            method.invoke(target);
        } catch (ReflectiveOperationException ex) {
            throw new AssertionError("cannot invoke " + name, ex);
        }
    }
}
