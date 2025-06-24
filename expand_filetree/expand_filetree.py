import mobase
from PyQt6.QtWidgets import QTreeView, QApplication
from PyQt6.QtCore import QTimer, QModelIndex, QObject

class ExpandFileTree(mobase.IPlugin):
    def __init__(self):
        super().__init__()
        self._organizer = None
        self._tree_model = None
        self._dialog_tree = None
        self._expand_timer = QTimer()
        self._expand_timer.setSingleShot(True)
        # Timer connected to the expansion method
        self._expand_timer.timeout.connect(self._do_expand_all)

        # Specific timer and related attributes for retrying to find the OverwriteInfoDialog tree
        self._overwrite_retry_timer = QTimer()
        self._overwrite_retry_timer.setSingleShot(True)
        self._overwrite_retry_timer.timeout.connect(self._retry_find_overwrite_tree)
        self._overwrite_dialog_ref = None  # Reference to the OverwriteInfoDialog
        self._retry_count = 0
        self._max_retries = 10  # Max attempts to find the tree
        self._retry_delay_ms = 200 # Initial delay for retries

    def name(self):
        return "ExpandFileTree"

    def author(self):
        return "BluBallZ"

    def description(self):
        return "Automatically Expands The File Tree."

    def version(self):
        return mobase.VersionInfo(1, 3, 0, mobase.ReleaseType.final)

    def isActive(self):
        return True

    def settings(self):
        return []

    def init(self, organizer):
        self._organizer = organizer
        app = QApplication.instance()
        if app:
            try:
                # Disconnect existing focusChanged connections to prevent duplicates
                app.focusChanged.disconnect(self.onFocusChanged)
            except (TypeError, RuntimeError):
                pass
            # Connect to focusChanged signal to detect dialog openings
            app.focusChanged.connect(self.onFocusChanged)
        return True

    def onFocusChanged(self, old, new):
        # Ensure the plugin is enabled
        if not self._organizer.isPluginEnabled(self.name()):
            return

        if new and new.window():
            dialog = new.window()
            dialog_class = dialog.metaObject().className()
            
            # Stop any pending overwrite retries if focus moves to a new dialog
            self._overwrite_retry_timer.stop()
            self._overwrite_dialog_ref = None
            self._retry_count = 0

            # Process file trees for specific dialog types
            if dialog_class in ["ModInfoDialog", "InstallDialog", "OverwriteInfoDialog"]:
                try:
                    # Disconnect existing destroyed connections to prevent duplicates
                    dialog.destroyed.disconnect(self.onDialogDestroyed)
                except (TypeError, RuntimeError):
                    pass
                # Connect to dialog's destroyed signal for cleanup
                dialog.destroyed.connect(self.onDialogDestroyed)
                self.processFileTree(dialog, dialog_class)

    def onDialogDestroyed(self):
        # Disconnect signals from the tree model when the associated dialog is destroyed
        if self._tree_model:
            try:
                self._tree_model.rowsInserted.disconnect(self.onRowsInserted)
            except (TypeError, RuntimeError):
                pass
            try:
                self._tree_model.rowsRemoved.disconnect(self.onRowsRemoved)
            except (TypeError, RuntimeError):
                pass
            try:
                self._tree_model.modelReset.disconnect(self.onModelReset)
            except (TypeError, RuntimeError):
                pass
        # Reset internal references and stop timers
        self._dialog_tree = None
        self._tree_model = None
        self._expand_timer.stop()
        self._overwrite_retry_timer.stop()
        self._overwrite_dialog_ref = None
        self._retry_count = 0

    def processFileTree(self, dialog, dialog_class):
        treeView = None
        if dialog_class == "ModInfoDialog":
            # For ModInfoDialog, specifically look for the QTreeView named "filetree"
            treeView = dialog.findChild(QTreeView, "filetree")
        elif dialog_class in ["InstallDialog", "OverwriteInfoDialog"]:
            # For these dialogs, find any QTreeView among the dialog's descendants
            all_tree_views = dialog.findChildren(QTreeView)
            if all_tree_views:
                treeView = all_tree_views[0] # Take the first QTreeView found
            else:
                # If no treeView found initially and it's the OverwriteInfoDialog,
                # start the persistent retry mechanism
                if dialog_class == "OverwriteInfoDialog":
                    self._overwrite_dialog_ref = dialog
                    self._retry_count = 0
                    self._overwrite_retry_timer.start(self._retry_delay_ms)
                    return # Exit this call, retry method will handle finding and processing

        if treeView:
            # If the found treeView is the same as the one already being processed, do nothing
            if treeView == self._dialog_tree and treeView.model() == self._tree_model:
                return
            
            # Disconnect signals from any previously processed model to prevent multiple connections
            if self._tree_model:
                try:
                    self._tree_model.rowsInserted.disconnect(self.onRowsInserted)
                except (TypeError, RuntimeError):
                    pass
                try:
                    self._tree_model.rowsRemoved.disconnect(self.onRowsRemoved)
                except (TypeError, RuntimeError):
                    pass
                try:
                    self._tree_model.modelReset.disconnect(self.onModelReset)
                except (TypeError, RuntimeError):
                    pass
            
            # Update internal references to the new treeView and its model
            self._dialog_tree = treeView
            model = treeView.model()
            if model:
                self._tree_model = model
                # Connect signals to the new model for dynamic expansion based on data changes
                self._tree_model.rowsInserted.connect(self.onRowsInserted)
                self._tree_model.rowsRemoved.connect(self.onRowsRemoved)
                self._tree_model.modelReset.connect(self.onModelReset)
                # Trigger initial expansion after a short delay to allow UI to settle
                QTimer.singleShot(50, lambda: self._trigger_expand())
            else:
                # If no model is found for the treeView, reset references
                self._dialog_tree = None

        # For dialogs other than OverwriteInfoDialog, if no treeView is found immediately,
        # try again after a short delay. This handles cases where the treeView might be created later.
        elif dialog_class != "OverwriteInfoDialog":
            QTimer.singleShot(50, lambda: self.processFileTree(dialog, dialog_class))


    def _retry_find_overwrite_tree(self):
        # Stop retrying if the dialog reference is lost or maximum retries are reached
        if not self._overwrite_dialog_ref or self._retry_count >= self._max_retries:
            self._overwrite_retry_timer.stop()
            self._overwrite_dialog_ref = None
            return

        self._retry_count += 1
        # Increase the delay for subsequent retries to give more time
        current_delay = self._retry_delay_ms + (self._retry_count * 50)
        
        # Attempt to find the QTreeView again within the overwrite dialog
        all_tree_views = self._overwrite_dialog_ref.findChildren(QTreeView)
        if all_tree_views:
            treeView = all_tree_views[0]
            self._overwrite_retry_timer.stop() # Found it, stop the retry timer
            # Process the found treeView as if it was found immediately
            # Pass the original dialog reference and its correct class name
            self.processFileTree(self._overwrite_dialog_ref, "OverwriteInfoDialog")
        else:
            # If not found yet, reschedule the retry with the increased delay
            self._overwrite_retry_timer.start(current_delay)

    def _trigger_expand(self):
        if self._dialog_tree and self._tree_model:
            try:
                # Check if the treeView object is still valid and visible
                _ = self._dialog_tree.isVisible()
                # Start the expansion timer with a delay to ensure UI readiness
                self._expand_timer.start(50)
            except RuntimeError:
                # If the treeView is no longer valid (e.g., dialog closed), reset references
                self._dialog_tree = None
                self._tree_model = None

    def _do_expand_all(self):
        if self._dialog_tree and self._tree_model:
            try:
                # Perform the actual expansion of all nodes in the tree
                self._dialog_tree.expandAll()
            except RuntimeError as e:
                # Handle cases where the treeView becomes invalid during expansion
                self._dialog_tree = None
                self._tree_model = None

    def onRowsInserted(self, parent_index: QModelIndex, first: int, last: int):
        # Trigger expansion when new rows are inserted into the model
        if not self._organizer.isPluginEnabled(self.name()):
            return
        if self._dialog_tree and self._tree_model == self._dialog_tree.model():
            self._trigger_expand()

    def onRowsRemoved(self, parent_index: QModelIndex, first: int, last: int):
        # Trigger expansion when rows are removed from the model
        if not self._organizer.isPluginEnabled(self.name()):
            return
        if self._dialog_tree and self._tree_model == self._dialog_tree.model():
            self._trigger_expand()

    def onModelReset(self):
        # Trigger expansion when the model is completely reset
        if not self._organizer.isPluginEnabled(self.name()):
            return
        if self._dialog_tree and self._tree_model == self._dialog_tree.model():
            self._trigger_expand()

