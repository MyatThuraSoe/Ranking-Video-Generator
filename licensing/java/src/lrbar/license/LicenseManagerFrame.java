package lrbar.license;

import javax.imageio.ImageIO;
import javax.swing.BorderFactory;
import javax.swing.ButtonGroup;
import javax.swing.JButton;
import javax.swing.JComponent;
import javax.swing.JDialog;
import javax.swing.JFileChooser;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JRadioButton;
import javax.swing.JScrollPane;
import javax.swing.JSpinner;
import javax.swing.JTabbedPane;
import javax.swing.JTable;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.JViewport;
import javax.swing.ListSelectionModel;
import javax.swing.RowFilter;
import javax.swing.Scrollable;
import javax.swing.ScrollPaneConstants;
import javax.swing.SpinnerNumberModel;
import javax.swing.SwingConstants;
import javax.swing.SwingUtilities;
import javax.swing.event.DocumentEvent;
import javax.swing.event.DocumentListener;
import javax.swing.table.AbstractTableModel;
import javax.swing.table.TableRowSorter;
import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.awt.LayoutManager;
import java.awt.Point;
import java.awt.Rectangle;
import java.awt.Toolkit;
import java.awt.datatransfer.StringSelection;
import java.awt.event.ActionEvent;
import java.awt.event.KeyEvent;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/** Main window: "Generate Key" and "History / Records" tabs. */
public final class LicenseManagerFrame extends JFrame {

    private final RecordStore store;

    // Generate tab
    private JTextField accountField;
    private JTextField machineField;
    private JTextField phoneField;
    private JTextArea noteArea;
    private JRadioButton dayRadio;
    private JRadioButton lifetimeRadio;
    private JSpinner daysSpinner;
    private JSpinner videosSpinner;
    private JLabel validityHint;
    private JTextArea resultArea;
    private JButton copyBtn;
    private JButton saveBtn;
    private JLabel statusLabel;
    private String currentKey = "";
    private JScrollPane generateScroller;
    private JPanel resultCard;

    // History tab
    private HistoryModel model;
    private JTable table;
    private TableRowSorter<HistoryModel> sorter;
    private JTextField searchField;
    private JLabel countLabel;
    private JButton copySelectedBtn;
    private JButton detailsBtn;
    private JButton deleteBtn;

    public LicenseManagerFrame() {
        super("LRBar-RankGen \u00b7 License Manager");
        this.store = new RecordStore(AppPaths.recordsFile());
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setMinimumSize(new Dimension(860, 660));
        Dimension screen = Toolkit.getDefaultToolkit().getScreenSize();
        int width = Math.min(1000, Math.max(880, screen.width - 120));
        int height = Math.min(790, Math.max(690, screen.height - 100));
        setSize(width, height);
        setLocationRelativeTo(null);
        loadWindowIcon();
        buildUi();
        refreshHistory();
        checkPrivateKey();
    }

    private void loadWindowIcon() {
        try {
            Path candidate = AppPaths.licensingDir().getParent()
                    .resolve("ranking_video_studio").resolve("packaging")
                    .resolve("app_icon.png");
            if (Files.isRegularFile(candidate)) {
                setIconImage(ImageIO.read(candidate.toFile()));
            }
        } catch (IOException | RuntimeException ignored) {
            // icon is optional
        }
    }

    private void checkPrivateKey() {
        Path key = AppPaths.privateKeyFile();
        if (!Files.isRegularFile(key)) {
            Theme.setStatus(statusLabel,
                    "private_key.pem was not found at " + key
                            + " \u2014 restore it before generating keys.", true);
        }
    }

    // ------------------------------------------------------------- structure
    private void buildUi() {
        JPanel root = new JPanel(new BorderLayout(0, 12));
        root.setBackground(Theme.BG);
        root.setBorder(BorderFactory.createEmptyBorder(18, 18, 16, 18));

        root.add(buildHeader(), BorderLayout.NORTH);

        JTabbedPane tabs = new JTabbedPane();
        tabs.setFont(Theme.BOLD);
        tabs.addTab("Generate Key", buildGenerateTab());
        tabs.addTab("History / Records", buildHistoryTab());
        tabs.addChangeListener(e -> {
            if (tabs.getSelectedIndex() == 1) {
                refreshHistory();
            }
        });
        root.add(tabs, BorderLayout.CENTER);

        setContentPane(root);

        getRootPane().getInputMap(JPanel.WHEN_IN_FOCUSED_WINDOW)
                .put(javax.swing.KeyStroke.getKeyStroke(KeyEvent.VK_ENTER,
                        Toolkit.getDefaultToolkit().getMenuShortcutKeyMaskEx()), "generate");
        getRootPane().getActionMap().put("generate",
                new javax.swing.AbstractAction() {
                    @Override
                    public void actionPerformed(ActionEvent e) {
                        generateKey();
                    }
                });
    }

    private JPanel buildHeader() {
        JPanel header = new JPanel(new BorderLayout(0, 3));
        header.setBackground(Theme.BG);
        header.add(Theme.title("License Manager"), BorderLayout.NORTH);
        header.add(Theme.subtitle(
                "Issue machine-bound license keys and keep a local record of every sale. "
                        + "Keys are signed offline with your private key."),
                BorderLayout.CENTER);
        return header;
    }

    // ---------------------------------------------------------- generate tab
    private JPanel buildGenerateTab() {
        // A scrollable column: on short screens the form keeps its natural
        // height and the key card below it stays fully visible once scrolled to.
        JPanel outer = new ScrollablePanel(new BorderLayout(0, 12));
        outer.setBackground(Theme.BG);
        outer.setBorder(BorderFactory.createEmptyBorder(12, 4, 4, 4));

        JPanel form = Theme.card();
        form.setLayout(new GridBagLayout());
        int row = 0;

        accountField = Theme.textField();
        accountField.setToolTipText("Optional customer name or business name");
        addFormRow(form, row++, "Account name", accountField, null,
                (JComponent) Theme.hint("Optional"));

        machineField = Theme.monoField();
        machineField.setToolTipText(
                "The ID the customer copied from the activation window");
        JButton pasteBtn = Theme.button("Paste");
        pasteBtn.setToolTipText("Paste the Machine ID from the clipboard");
        pasteBtn.addActionListener(e -> pasteInto(machineField));
        addFormRow(form, row++, "Machine ID *", machineField, pasteBtn,
                (JComponent) Theme.hint(
                        "Required \u2014 20 hex characters, e.g. 7F3A-9C2E-1B44-D07A-55C1"));

        phoneField = Theme.textField();
        phoneField.setToolTipText("Optional phone / WhatsApp number");
        addFormRow(form, row++, "Phone number", phoneField, null,
                (JComponent) Theme.hint("Optional"));

        noteArea = Theme.textArea();
        noteArea.setRows(2);
        noteArea.setToolTipText("Optional order details, platform, etc.");
        JScrollPane noteScroll = Theme.scroll(noteArea);
        noteScroll.setPreferredSize(new Dimension(200, 52));
        addFormRow(form, row++, "Note", noteScroll, null,
                (JComponent) Theme.hint("Optional"));

        dayRadio = radio("1-Day", true);
        lifetimeRadio = radio("Lifetime", false);
        ButtonGroup group = new ButtonGroup();
        group.add(dayRadio);
        group.add(lifetimeRadio);
        dayRadio.addActionListener(e -> updateTypeControls());
        lifetimeRadio.addActionListener(e -> updateTypeControls());

        daysSpinner = new JSpinner(new SpinnerNumberModel(1, 1, 365, 1));
        videosSpinner = new JSpinner(new SpinnerNumberModel(
                LicenseIssuer.DEFAULT_VIDEOS, 1, 1000, 1));
        Theme.styleSpinner(daysSpinner);
        Theme.styleSpinner(videosSpinner);

        JPanel typePanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 12, 2));
        typePanel.setOpaque(false);
        typePanel.add(dayRadio);
        typePanel.add(lifetimeRadio);
        typePanel.add(javax.swing.Box.createHorizontalStrut(8));
        typePanel.add(daysSpinner);
        typePanel.add(Theme.hint("day(s)"));
        typePanel.add(javax.swing.Box.createHorizontalStrut(8));
        typePanel.add(videosSpinner);
        typePanel.add(Theme.hint("video exports"));
        validityHint = Theme.hint(
                "1-Day keys expire 24 hours after generation and allow 2 video exports.");
        addFormRow(form, row++, "License type", typePanel, null, validityHint);

        JButton generateBtn = Theme.primaryButton("Generate License Key");
        generateBtn.setToolTipText("Sign a key for the Machine ID above");
        generateBtn.addActionListener(e -> generateKey());
        GridBagConstraints gc = new GridBagConstraints();
        gc.gridy = row;
        gc.gridx = 1;
        gc.weightx = 1;
        gc.fill = GridBagConstraints.HORIZONTAL;
        gc.insets = new Insets(8, 0, 2, 0);
        form.add(generateBtn, gc);

        resultCard = buildResultCard();

        outer.add(form, BorderLayout.NORTH);
        outer.add(resultCard, BorderLayout.CENTER);

        generateScroller = new JScrollPane(outer,
                ScrollPaneConstants.VERTICAL_SCROLLBAR_AS_NEEDED,
                ScrollPaneConstants.HORIZONTAL_SCROLLBAR_NEVER);
        generateScroller.setBorder(BorderFactory.createEmptyBorder());
        generateScroller.setBackground(Theme.BG);
        generateScroller.getViewport().setBackground(Theme.BG);
        generateScroller.getViewport().setScrollMode(JViewport.BLIT_SCROLL_MODE);
        generateScroller.getVerticalScrollBar().setUnitIncrement(18);

        JPanel tab = new JPanel(new BorderLayout());
        tab.setBackground(Theme.BG);
        tab.add(generateScroller, BorderLayout.CENTER);
        return tab;
    }

    /** Keeps the form at its natural height and tracks the viewport width. */
    private static final class ScrollablePanel extends JPanel implements Scrollable {

        ScrollablePanel(LayoutManager layout) {
            super(layout);
            setOpaque(true);
        }

        @Override
        public Dimension getPreferredScrollableViewportSize() {
            return getPreferredSize();
        }

        @Override
        public int getScrollableUnitIncrement(Rectangle visibleRect, int orientation,
                                              int direction) {
            return 18;
        }

        @Override
        public int getScrollableBlockIncrement(Rectangle visibleRect, int orientation,
                                               int direction) {
            return Math.max(18, visibleRect.height - 36);
        }

        @Override
        public boolean getScrollableTracksViewportWidth() {
            return true;
        }

        @Override
        public boolean getScrollableTracksViewportHeight() {
            return false;
        }
    }

    private JPanel buildResultCard() {
        JPanel card = Theme.card();
        card.setLayout(new BorderLayout(0, 10));

        JPanel head = new JPanel(new BorderLayout());
        head.setOpaque(false);
        head.add(Theme.fieldLabel("License key to send to the customer"),
                BorderLayout.WEST);
        JPanel actions = new JPanel(new FlowLayout(FlowLayout.RIGHT, 8, 0));
        actions.setOpaque(false);
        copyBtn = Theme.button("Copy Key");
        copyBtn.setEnabled(false);
        copyBtn.addActionListener(e -> {
            if (!currentKey.isBlank()) {
                copyText(currentKey);
                Theme.setStatus(statusLabel,
                        "License key copied to the clipboard.", false);
            }
        });
        saveBtn = Theme.button("Save as .txt\u2026");
        saveBtn.setEnabled(false);
        saveBtn.addActionListener(e -> saveCurrentKey());
        actions.add(copyBtn);
        actions.add(saveBtn);
        head.add(actions, BorderLayout.EAST);
        card.add(head, BorderLayout.NORTH);

        resultArea = Theme.monoArea();
        resultArea.setRows(4);
        resultArea.setEditable(false);
        resultArea.setLineWrap(true);
        resultArea.setWrapStyleWord(false);
        resultArea.setToolTipText("Send this whole line to the customer");
        JScrollPane keyScroll = Theme.scroll(resultArea);
        keyScroll.setPreferredSize(new Dimension(200, 96));
        card.add(keyScroll, BorderLayout.CENTER);

        statusLabel = new JLabel("");
        statusLabel.setFont(Theme.SUBTITLE);
        statusLabel.setForeground(Theme.OK);
        statusLabel.setVisible(false);
        card.add(statusLabel, BorderLayout.SOUTH);
        return card;
    }

    private static JRadioButton radio(String text, boolean selected) {
        JRadioButton button = new JRadioButton(text, selected);
        button.setFont(Theme.UI);
        button.setForeground(Theme.TEXT_SOFT);
        button.setOpaque(false);
        button.setFocusPainted(false);
        return button;
    }

    private void addFormRow(JPanel form, int row, String labelText,
                            java.awt.Component field, java.awt.Component extra,
                            JComponent hint) {
        GridBagConstraints left = new GridBagConstraints();
        left.gridx = 0;
        left.gridy = row;
        left.anchor = GridBagConstraints.NORTHWEST;
        left.insets = new Insets(5, 0, 5, 14);
        JLabel label = Theme.fieldLabel(labelText);
        label.setHorizontalAlignment(SwingConstants.RIGHT);
        label.setPreferredSize(new Dimension(126, 30));
        form.add(label, left);

        JPanel wrap = new JPanel(new BorderLayout(8, 3));
        wrap.setOpaque(false);
        if (extra != null) {
            JPanel line = new JPanel(new BorderLayout(8, 0));
            line.setOpaque(false);
            line.add(field, BorderLayout.CENTER);
            line.add(extra, BorderLayout.EAST);
            wrap.add(line, BorderLayout.CENTER);
        } else {
            wrap.add(field, BorderLayout.CENTER);
        }
        if (hint != null) {
            wrap.add(hint, BorderLayout.SOUTH);
        }

        GridBagConstraints right = new GridBagConstraints();
        right.gridx = 1;
        right.gridy = row;
        right.weightx = 1;
        right.fill = GridBagConstraints.HORIZONTAL;
        right.anchor = GridBagConstraints.WEST;
        right.insets = new Insets(5, 0, 5, 0);
        form.add(wrap, right);
    }

    private void updateTypeControls() {
        boolean day = dayRadio.isSelected();
        daysSpinner.setEnabled(day);
        videosSpinner.setEnabled(day);
        validityHint.setText(day
                ? "1-Day keys expire 24 hours after generation and allow 2 video exports."
                : "Lifetime keys never expire and allow unlimited exports.");
    }

    private void pasteInto(JTextField field) {
        String text = readClipboard();
        if (text != null && !text.isBlank()) {
            field.setText(text.trim());
            field.requestFocusInWindow();
        }
    }

    private static String readClipboard() {
        try {
            Object data = Toolkit.getDefaultToolkit().getSystemClipboard()
                    .getData(java.awt.datatransfer.DataFlavor.stringFlavor);
            return data == null ? "" : data.toString();
        } catch (Exception ex) {
            return "";
        }
    }

    // ------------------------------------------------------------- generating
    private void generateKey() {
        String machine = MachineId.normalize(machineField.getText());
        if (machine.isEmpty()) {
            machineField.requestFocusInWindow();
            Theme.setStatus(statusLabel,
                    "Enter the customer's Machine ID: 20 hexadecimal characters "
                            + "(for example 7F3A-9C2E-1B44-D07A-55C1).", true);
            return;
        }
        machineField.setText(machine);

        String kind = dayRadio.isSelected()
                ? LicenseIssuer.DAY : LicenseIssuer.LIFETIME;
        int days = (Integer) daysSpinner.getValue();
        int videos = (Integer) videosSpinner.getValue();
        String note = noteArea.getText().trim();

        try {
            LicenseIssuer.Issued issued = LicenseIssuer.issue(
                    AppPaths.privateKeyFile(), machine, kind, days, videos, note);

            Record record = new Record();
            record.licenseId = issued.licenseId;
            record.createdAt = Record.nowDisplay();
            record.createdAtEpoch = Instant.now().getEpochSecond();
            record.machineId = machine;
            record.accountName = accountField.getText().trim();
            record.phone = phoneField.getText().trim();
            record.note = note;
            record.type = kind;
            record.issuedAt = issued.issuedAt;
            record.expiresAt = issued.expiresAt;
            record.days = LicenseIssuer.LIFETIME.equals(kind)
                    ? 0 : Math.max(1, days);
            record.videos = issued.videos;
            record.key = issued.key;
            boolean saved = store.add(record);

            currentKey = issued.key;
            resultArea.setText(issued.key);
            resultArea.setCaretPosition(0);
            copyBtn.setEnabled(true);
            saveBtn.setEnabled(true);
            if (saved) {
                Theme.setStatus(statusLabel,
                        "Key issued and saved to history \u00b7 License ID "
                                + issued.licenseId + " \u00b7 "
                                + record.typeLabel() + ".", false);
            } else {
                Theme.setStatus(statusLabel,
                        "Key issued, but the history file could not be saved ("
                                + store.lastError()
                                + "). Copy the key now and check folder permissions.",
                        true);
            }
            refreshHistory();
            revealResult();
        } catch (Exception ex) {
            currentKey = "";
            resultArea.setText("");
            copyBtn.setEnabled(false);
            saveBtn.setEnabled(false);
            Theme.setStatus(statusLabel, ex.getMessage(), true);
            revealResult();
            JOptionPane.showMessageDialog(this, ex.getMessage(),
                    "Could not generate key", JOptionPane.ERROR_MESSAGE);
        }
    }

    /** Scroll the generate tab down to the key card (no-op when it already fits). */
    private void revealResult() {
        if (generateScroller == null) {
            return;
        }
        SwingUtilities.invokeLater(() -> {
            JViewport viewport = generateScroller.getViewport();
            int max = viewport.getViewSize().height - viewport.getExtentSize().height;
            if (max > 0) {
                viewport.setViewPosition(new Point(0, max));
            }
        });
    }

    private void saveCurrentKey() {
        if (currentKey.isBlank()) {
            return;
        }
        String machine = MachineId.normalize(machineField.getText());
        JFileChooser chooser = new JFileChooser();
        chooser.setDialogTitle("Save license key");
        chooser.setSelectedFile(new File(
                "LRBar-RankGen-" + (machine.isEmpty() ? "license" : machine) + ".txt"));
        if (chooser.showSaveDialog(this) != JFileChooser.APPROVE_OPTION) {
            return;
        }
        Path path = chooser.getSelectedFile().toPath();
        if (!path.getFileName().toString().toLowerCase().endsWith(".txt")) {
            path = path.resolveSibling(path.getFileName() + ".txt");
        }
        try {
            Files.writeString(path, currentKey + "\n", StandardCharsets.UTF_8);
            Theme.setStatus(statusLabel, "Key saved to " + path, false);
        } catch (IOException ex) {
            JOptionPane.showMessageDialog(this,
                    "Could not save the file:\n" + ex.getMessage(),
                    "Save failed", JOptionPane.ERROR_MESSAGE);
        }
    }

    // -------------------------------------------------------------- history
    private JPanel buildHistoryTab() {
        JPanel outer = new JPanel(new BorderLayout(0, 12));
        outer.setBackground(Theme.BG);
        outer.setBorder(BorderFactory.createEmptyBorder(16, 4, 4, 4));

        JPanel top = new JPanel(new BorderLayout(14, 0));
        top.setOpaque(false);
        JPanel searchBox = new JPanel(new BorderLayout(8, 0));
        searchBox.setOpaque(false);
        searchBox.add(Theme.fieldLabel("Search"), BorderLayout.WEST);
        searchField = Theme.textField();
        searchField.setToolTipText(
                "Filter by account, Machine ID, phone, note, type or date");
        searchField.getDocument().addDocumentListener(new DocumentListener() {
            @Override
            public void insertUpdate(DocumentEvent e) {
                applyFilter();
            }

            @Override
            public void removeUpdate(DocumentEvent e) {
                applyFilter();
            }

            @Override
            public void changedUpdate(DocumentEvent e) {
                applyFilter();
            }
        });
        searchBox.add(searchField, BorderLayout.CENTER);
        top.add(searchBox, BorderLayout.CENTER);

        JPanel topActions = new JPanel(new FlowLayout(FlowLayout.RIGHT, 8, 0));
        topActions.setOpaque(false);
        JButton refreshBtn = Theme.button("Refresh");
        refreshBtn.addActionListener(e -> refreshHistory());
        JButton exportBtn = Theme.button("Export CSV\u2026");
        exportBtn.addActionListener(e -> exportCsv());
        topActions.add(refreshBtn);
        topActions.add(exportBtn);
        top.add(topActions, BorderLayout.EAST);

        model = new HistoryModel();
        table = new JTable(model);
        Theme.styleTable(table);
        table.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);
        sorter = new TableRowSorter<>(model);
        table.setRowSorter(sorter);
        int[] widths = {148, 130, 156, 100, 74, 148, 82, 92};
        for (int i = 0; i < widths.length; i++) {
            table.getColumnModel().getColumn(i).setPreferredWidth(widths[i]);
        }
        table.addMouseListener(new MouseAdapter() {
            @Override
            public void mouseClicked(MouseEvent e) {
                if (e.getClickCount() == 2) {
                    showSelectedDetails();
                }
            }
        });

        JPanel bottom = new JPanel(new BorderLayout(12, 0));
        bottom.setOpaque(false);
        countLabel = Theme.hint("0 records");
        bottom.add(countLabel, BorderLayout.WEST);

        JPanel bottomActions = new JPanel(new FlowLayout(FlowLayout.RIGHT, 8, 0));
        bottomActions.setOpaque(false);
        copySelectedBtn = Theme.button("Copy Key");
        copySelectedBtn.addActionListener(e -> copySelectedKey());
        detailsBtn = Theme.button("Details\u2026");
        detailsBtn.addActionListener(e -> showSelectedDetails());
        deleteBtn = Theme.dangerButton("Delete");
        deleteBtn.addActionListener(e -> deleteSelected());
        bottomActions.add(copySelectedBtn);
        bottomActions.add(detailsBtn);
        bottomActions.add(deleteBtn);
        bottom.add(bottomActions, BorderLayout.EAST);

        JPanel center = new JPanel(new BorderLayout());
        center.setOpaque(false);
        center.add(Theme.scroll(table), BorderLayout.CENTER);

        outer.add(top, BorderLayout.NORTH);
        outer.add(center, BorderLayout.CENTER);
        outer.add(bottom, BorderLayout.SOUTH);
        return outer;
    }

    private void refreshHistory() {
        model.setRecords(store.all());
        applyFilter();
    }

    private void applyFilter() {
        if (sorter == null) {
            return;
        }
        String query = searchField == null ? "" : searchField.getText().trim();
        if (query.isEmpty()) {
            sorter.setRowFilter(null);
        } else {
            sorter.setRowFilter(RowFilter.regexFilter("(?i)" + Pattern.quote(query)));
        }
        updateCountLabel();
    }

    private void updateCountLabel() {
        if (countLabel == null || model == null || table == null) {
            return;
        }
        int shown = table.getRowCount();
        int total = model.getRowCount();
        if (shown == total) {
            countLabel.setText(total + (total == 1 ? " record" : " records"));
        } else {
            countLabel.setText(shown + " of " + total + " record"
                    + (total == 1 ? "" : "s"));
        }
    }

    private Record selectedRecord() {
        int viewRow = table.getSelectedRow();
        if (viewRow < 0) {
            JOptionPane.showMessageDialog(this,
                    "Select a record in the table first.",
                    "No record selected", JOptionPane.INFORMATION_MESSAGE);
            return null;
        }
        return model.at(table.convertRowIndexToModel(viewRow));
    }

    private void copySelectedKey() {
        Record record = selectedRecord();
        if (record == null) {
            return;
        }
        copyText(record.key);
        flashCount("License key copied to the clipboard.");
    }

    private void flashCount(String message) {
        countLabel.setText(message);
        countLabel.setForeground(Theme.OK);
        javax.swing.Timer timer = new javax.swing.Timer(1800, e -> {
            countLabel.setForeground(Theme.DIM);
            updateCountLabel();
        });
        timer.setRepeats(false);
        timer.start();
    }

    private void deleteSelected() {
        Record record = selectedRecord();
        if (record == null) {
            return;
        }
        int answer = JOptionPane.showConfirmDialog(this,
                "Delete this record?\n\n" + record.machineId + " \u00b7 "
                        + record.typeLabel() + " \u00b7 " + record.createdAt
                        + "\n\nThe license key itself keeps working; only the "
                        + "local history entry is removed.",
                "Delete record", JOptionPane.YES_NO_OPTION,
                JOptionPane.WARNING_MESSAGE);
        if (answer != JOptionPane.YES_OPTION) {
            return;
        }
        store.remove(record);
        refreshHistory();
        flashCount("Record deleted.");
    }

    private void showSelectedDetails() {
        Record record = selectedRecord();
        if (record != null) {
            showDetails(record);
        }
    }

    private void showDetails(Record record) {
        JDialog dialog = new JDialog(this,
                "License details \u00b7 " + record.licenseId, true);
        dialog.setDefaultCloseOperation(JDialog.DISPOSE_ON_CLOSE);

        JPanel root = new JPanel(new BorderLayout(0, 12));
        root.setBackground(Theme.BG);
        root.setBorder(BorderFactory.createEmptyBorder(18, 18, 16, 18));

        JPanel info = Theme.card();
        info.setLayout(new GridBagLayout());
        int row = 0;
        addDetailRow(info, row++, "Generated", record.createdAt);
        addDetailRow(info, row++, "Account", blankTo(record.accountName, "\u2014"));
        addDetailRow(info, row++, "Machine ID", record.machineId);
        addDetailRow(info, row++, "Phone", blankTo(record.phone, "\u2014"));
        addDetailRow(info, row++, "Type", record.typeLabel());
        addDetailRow(info, row++, "Expires", record.expiresLabel());
        addDetailRow(info, row++, "Video limit", record.videosLabel());
        addDetailRow(info, row++, "License ID", record.licenseId);
        addDetailRow(info, row++, "Note", blankTo(record.note, "\u2014"));

        JPanel keyPanel = Theme.card();
        keyPanel.setLayout(new BorderLayout(0, 8));
        keyPanel.add(Theme.fieldLabel("License key"), BorderLayout.NORTH);
        JTextArea keyArea = Theme.monoArea();
        keyArea.setText(record.key);
        keyArea.setEditable(false);
        keyArea.setLineWrap(true);
        keyArea.setRows(4);
        keyArea.setCaretPosition(0);
        keyPanel.add(Theme.scroll(keyArea), BorderLayout.CENTER);

        JPanel buttons = new JPanel(new FlowLayout(FlowLayout.RIGHT, 8, 0));
        buttons.setOpaque(false);
        JButton copy = Theme.primaryButton("Copy Key");
        copy.addActionListener(e -> {
            copyText(record.key);
            copy.setText("Copied \u2713");
        });
        JButton close = Theme.button("Close");
        close.addActionListener(e -> dialog.dispose());
        buttons.add(close);
        buttons.add(copy);

        root.add(info, BorderLayout.NORTH);
        root.add(keyPanel, BorderLayout.CENTER);
        root.add(buttons, BorderLayout.SOUTH);

        dialog.setContentPane(root);
        dialog.setSize(760, 560);
        dialog.setMinimumSize(new Dimension(640, 480));
        dialog.setLocationRelativeTo(this);
        dialog.setVisible(true);
    }

    private void addDetailRow(JPanel panel, int row, String label, String value) {
        GridBagConstraints left = new GridBagConstraints();
        left.gridx = 0;
        left.gridy = row;
        left.anchor = GridBagConstraints.WEST;
        left.insets = new Insets(3, 0, 3, 16);
        JLabel caption = Theme.fieldLabel(label);
        caption.setHorizontalAlignment(SwingConstants.RIGHT);
        caption.setPreferredSize(new Dimension(112, 22));
        panel.add(caption, left);

        GridBagConstraints right = new GridBagConstraints();
        right.gridx = 1;
        right.gridy = row;
        right.weightx = 1;
        right.fill = GridBagConstraints.HORIZONTAL;
        right.anchor = GridBagConstraints.WEST;
        right.insets = new Insets(3, 0, 3, 0);
        JLabel field = Theme.label(value);
        boolean mono = "Machine ID".equals(label) || "License ID".equals(label);
        field.setFont(mono
                ? new Font("Consolas", Font.PLAIN, 12) : Theme.UI);
        field.setToolTipText(value);
        panel.add(field, right);
    }

    private static String blankTo(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private void exportCsv() {
        JFileChooser chooser = new JFileChooser();
        chooser.setDialogTitle("Export license history");
        chooser.setSelectedFile(new File("license_records.csv"));
        if (chooser.showSaveDialog(this) != JFileChooser.APPROVE_OPTION) {
            return;
        }
        Path path = chooser.getSelectedFile().toPath();
        if (!path.getFileName().toString().toLowerCase().endsWith(".csv")) {
            path = path.resolveSibling(path.getFileName() + ".csv");
        }
        StringBuilder out = new StringBuilder();
        out.append("Generated,Account,Machine ID,Phone,Type,Expires,Videos,"
                + "License ID,Note,License Key\n");
        for (Record r : store.all()) {
            out.append(csv(r.createdAt)).append(',')
                    .append(csv(r.accountName)).append(',')
                    .append(csv(r.machineId)).append(',')
                    .append(csv(r.phone)).append(',')
                    .append(csv(r.typeLabel())).append(',')
                    .append(csv(r.expiresLabel())).append(',')
                    .append(csv(r.videosLabel())).append(',')
                    .append(csv(r.licenseId)).append(',')
                    .append(csv(r.note)).append(',')
                    .append(csv(r.key)).append('\n');
        }
        try {
            Files.writeString(path, out.toString(), StandardCharsets.UTF_8);
            flashCount("Exported " + store.size() + " record(s) to " + path);
        } catch (IOException ex) {
            JOptionPane.showMessageDialog(this,
                    "Could not export the CSV:\n" + ex.getMessage(),
                    "Export failed", JOptionPane.ERROR_MESSAGE);
        }
    }

    private static String csv(String value) {
        String text = value == null ? "" : value;
        if (text.indexOf(',') >= 0 || text.indexOf('"') >= 0
                || text.indexOf('\n') >= 0 || text.indexOf('\r') >= 0) {
            return '"' + text.replace("\"", "\"\"") + '"';
        }
        return text;
    }

    private static void copyText(String text) {
        Toolkit.getDefaultToolkit().getSystemClipboard()
                .setContents(new StringSelection(text == null ? "" : text), null);
    }

    // ----------------------------------------------------------- table model
    private static final class HistoryModel extends AbstractTableModel {

        private static final String[] COLUMNS = {
                "Generated", "Account", "Machine ID", "Phone", "Type",
                "Expires", "Videos", "License ID",
        };

        private List<Record> rows = new ArrayList<>();

        void setRecords(List<Record> records) {
            rows = new ArrayList<>(records);
            fireTableDataChanged();
        }

        Record at(int row) {
            return rows.get(row);
        }

        @Override
        public int getRowCount() {
            return rows.size();
        }

        @Override
        public int getColumnCount() {
            return COLUMNS.length;
        }

        @Override
        public String getColumnName(int column) {
            return COLUMNS[column];
        }

        @Override
        public Class<?> getColumnClass(int columnIndex) {
            return String.class;
        }

        @Override
        public boolean isCellEditable(int rowIndex, int columnIndex) {
            return false;
        }

        @Override
        public Object getValueAt(int rowIndex, int columnIndex) {
            Record r = rows.get(rowIndex);
            return switch (columnIndex) {
                case 0 -> r.createdAt;
                case 1 -> r.accountName;
                case 2 -> r.machineId;
                case 3 -> r.phone;
                case 4 -> r.typeLabel();
                case 5 -> r.expiresLabel();
                case 6 -> r.videosLabel();
                case 7 -> r.licenseId;
                default -> "";
            };
        }
    }
}
