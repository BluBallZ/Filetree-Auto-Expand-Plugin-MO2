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
        # Increased initial delay for _expand_timer
        self._expand_timer.timeout.connect(self._do_expand_all)

    def name(self):
        return "ExpandFileTree"

    def author(self):
        return "BluBallZ"

    def description(self):
        return "Automatically Expands The File Tree."

    def version(self):
        return mobase.VersionInfo(1, 0, 12, mobase.ReleaseType.final)

    def isActive(self):
        return True

    def settings(self):
        return []

    def init(self, organizer):
        self._organizer = organizer
        app = QApplication.instance()
        if app:
            try:
                app.focusChanged.disconnect(self.onFocusChanged)
            except (TypeError, RuntimeError):
                pass
            app.focusChanged.connect(self.onFocusChanged)
        return True

    def onFocusChanged(self, old, new):
        if not self._organizer.isPluginEnabled(self.name()):
            return
        if new and new.window():
            dialog = new.window()
            dialog_class = dialog.metaObject().className()
            if dialog_class in ["ModInfoDialog", "InstallDialog"]:
                try:
                    dialog.destroyed.disconnect(self.onDialogDestroyed)
                except (TypeError, RuntimeError):
                    pass
                dialog.destroyed.connect(self.onDialogDestroyed)
                self.processFileTree(dialog, dialog_class)

    def onDialogDestroyed(self):
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
        
        self._dialog_tree = None
        self._tree_model = None
        self._expand_timer.stop()

    def processFileTree(self, dialog, dialog_class):
        treeView = dialog.findChild(QTreeView, "filetree" if dialog_class == "ModInfoDialog" else None)
        if treeView:
            if treeView == self._dialog_tree and treeView.model() == self._tree_model:
                return

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

            self._dialog_tree = treeView
            model = treeView.model()

            if model:
                self._tree_model = model
                self._tree_model.rowsInserted.connect(self.onRowsInserted)
                self._tree_model.rowsRemoved.connect(self.onRowsRemoved)
                self._tree_model.modelReset.connect(self.onModelReset)

                # Initial expansion trigger
                QTimer.singleShot(50, lambda: self._trigger_expand())
            else:
                self._organizer.log(mobase.logLevel.Warning, f"No model found for treeView in {dialog_class}")
        else:
            QTimer.singleShot(200, lambda: self.processFileTree(dialog, dialog_class))

    def _trigger_expand(self):
        if self._dialog_tree and self._tree_model:
            try:
                # Check if the treeView is still accessible before starting the timer
                _ = self._dialog_tree.isVisible() 
                self._expand_timer.start(1) # <-- Try increasing this to 250ms, then 300ms, 500ms
            except RuntimeError:
                self._dialog_tree = None
                self._tree_model = None
                self._organizer.log(mobase.logLevel.Debug, "Dialog tree not valid when trying to trigger expand.")

    def _do_expand_all(self):
        if self._dialog_tree and self._tree_model:
            try:
                self._dialog_tree.expandAll()
            except RuntimeError as e:
                self._organizer.log(mobase.logLevel.Warning, f"Error expanding tree: {e}. Dialog tree likely deleted.")
                self._dialog_tree = None
                self._tree_model = None

    def onRowsInserted(self, parent_index: QModelIndex, first: int, last: int):
        if not self._organizer.isPluginEnabled(self.name()):
            return
        if self._dialog_tree and self._tree_model == self._dialog_tree.model():
            self._trigger_expand()

    def onRowsRemoved(self, parent_index: QModelIndex, first: int, last: int):
        if not self._organizer.isPluginEnabled(self.name()):
            return
        if self._dialog_tree and self._tree_model == self._dialog_tree.model():
            self._trigger_expand()

    def onModelReset(self):
        if not self._organizer.isPluginEnabled(self.name()):
            return
        if self._dialog_tree and self._tree_model == self._dialog_tree.model():
            self._trigger_expand()

    def isTreePartiallyExpanded(self, treeView):
        try:
            model = treeView.model()
            if not model:
                return False
            
            _ = model.rowCount(QModelIndex())

            for row in range(model.rowCount()):
                index = model.index(row, 0)
                if treeView.isExpanded(index) and model.hasChildren(index):
                    for child_row in range(model.rowCount(index)):
                        child_index = model.index(child_row, 0, index)
                        if model.hasChildren(child_index) and not treeView.isExpanded(child_index):
                            return True
            return False
        except RuntimeError:
            self._organizer.log(mobase.logLevel.Debug, "Model or treeView no longer valid in isTreePartiallyExpanded.")
            return False

    def expandFocusedTree(self):
        app = QApplication.instance()
        if app:
            focused_widget = app.focusWidget()
            if isinstance(focused_widget, QTreeView):
                try:
                    focused_widget.expandAll()
                except RuntimeError as e:
                    self._organizer.log(mobase.logLevel.Warning, f"Error expanding focused tree: {e}")
