import mobase
from PyQt6.QtWidgets import QTreeView, QApplication
from PyQt6.QtCore import QTimer, Qt

class ExpandFileTree(mobase.IPlugin):
    def __init__(self):
        super().__init__()
        self._organizer = None
        self._dialog_tree = None
        self._tree_model = None
        self._is_dragging = False  # Track drag state

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
        app.focusChanged.connect(self.onFocusChanged)
        return True

    def onFocusChanged(self, old, new):
        if not self._organizer.isPluginEnabled(self.name()):
            return
        if new and new.window():
            dialog = new.window()
            dialog_class = dialog.metaObject().className()
            if dialog_class in ["ModInfoDialog", "InstallDialog"]:
                dialog.destroyed.connect(self.onDialogDestroyed)
                self.expandFileTree(dialog, dialog_class)

    def onDialogDestroyed(self):
        self._dialog_tree = None
        self._tree_model = None

    def expandFileTree(self, dialog, dialog_class):
        treeView = dialog.findChild(QTreeView, "filetree" if dialog_class == "ModInfoDialog" else None)
        if treeView:
            self._dialog_tree = treeView
            # Explicitly enable drag-and-drop
            treeView.setDragEnabled(True)
            treeView.setAcceptDrops(True)
            treeView.setDropIndicatorShown(True)
            treeView.setDragDropMode(QTreeView.DragDropMode.DragDrop)
            # Connect drag-and-drop events to track state
            treeView.dragEnterEvent = self.onDragEnterEvent
            treeView.dropEvent = self.onDropEvent
            model = treeView.model()
            if model and model != self._tree_model:
                self._tree_model = model
                self._tree_model.rowsInserted.connect(self.onRowsInserted)
            QTimer.singleShot(50, lambda: self.expandAllLevels(treeView))
        else:
            QTimer.singleShot(200, lambda: self.expandFileTree(dialog, dialog_class))

    def onDragEnterEvent(self, event):
        self._is_dragging = True
        event.accept()  # Accept the drag event

    def onDropEvent(self, event):
        self._is_dragging = False
        event.accept()  # Accept the drop event
        # Re-expand tree after drop, if needed
        if self._dialog_tree:
            QTimer.singleShot(100, lambda: self.expandAllLevels(self._dialog_tree))

    def expandAllLevels(self, treeView):
        if self._is_dragging:
            return  # Skip expansion during drag-and-drop
        try:
            treeView.expandAll()
            # Only recheck if necessary, avoid infinite recursion
            if self.isTreePartiallyExpanded(treeView):
                QTimer.singleShot(100, lambda: self.expandAllLevels(treeView))
        except RuntimeError:
            return

    def isTreePartiallyExpanded(self, treeView):
        try:
            model = treeView.model()
            if not model:
                return False
            for row in range(model.rowCount()):
                index = model.index(row, 0)
                if treeView.isExpanded(index) and model.hasChildren(index):
                    for child_row in range(model.rowCount(index)):
                        child_index = model.index(child_row, 0, index)
                        if model.hasChildren(child_index) and not treeView.isExpanded(child_index):
                            return True
            return False
        except RuntimeError:
            return False

    def onRowsInserted(self, parent, first, last):
        if not self._organizer.isPluginEnabled(self.name()) or self._is_dragging:
            return
        if self._dialog_tree:
            QTimer.singleShot(0, lambda: self.expandAllLevels(self._dialog_tree))

    def expandFocusedTree(self):
        app = QApplication.instance()
        focused_widget = app.focusWidget()
        if isinstance(focused_widget, QTreeView) and not self._is_dragging:
            self.expandAllLevels(focused_widget)