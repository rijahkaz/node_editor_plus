import sys
from shiboken2 import wrapInstance
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from maya import mel, cmds, OpenMayaUI


def maya_main_window():
    """
    Return the Maya main window widget as a Python object
    """
    main_window_ptr = OpenMayaUI.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QWidget)


class NEPConnectionFilter(QDialog):

    def __init__(self, connection_type="input", parent=maya_main_window()):
        super(NEPConnectionFilter, self).__init__(parent)
        self.CATEGORY = ("Node", "Attribute", "Type")
        self.CONNECTION_TYPE = connection_type

        # TESTING DATA  TODO: use a zip method for real thing
        self.node_info = [["node1_postfix", "translateX", "abc"],
                          ["node2", "translateY", "123"],
                          ["node3", "translateY", "abc"],
                          ["transform1", "translateX\ntranslateY", "123"],
                          ["nice", "translateX", "123"],
                          ["prefix_ok", "translateY", "123"],
                          ["ok_postfix", "translateY", "abc"],
                          ["this is a very very very long name", "translateX", "abc"]]

        # sys.stdout.write(f"Attribute name {self.CONNECTION_TYPE}")
        cmds.inViewMessage(amg=f'Viewing "<hl>{self.CONNECTION_TYPE}</hl>"', pos='midCenter', fade=True)

        self.setMinimumSize(382, 600)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)

        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        # Corner resizing grips
        self.grips = []
        self.grip_size = 8
        for i in range(4):
            grip = QSizeGrip(self)
            grip.resize(self.grip_size, self.grip_size)
            self.grips.append(grip)

        self.window_label = QLabel(f"Node name: attr name {self.CONNECTION_TYPE}")
        self.window_label.setAlignment(Qt.AlignCenter)
        self.window_label.setStyleSheet("QLabel {font-size: 15px;}")

        self.exit_btn = QPushButton()
        icon_size = QImageReader(f":{self.CONNECTION_TYPE}.png").size()
        self.exit_btn.setIcon(QIcon(f":{self.CONNECTION_TYPE}.png"))
        self.exit_btn.setIconSize(QSize(icon_size))
        self.exit_btn.setFixedSize(icon_size.width(), icon_size.height())
        self.exit_btn.setStyleSheet("QPushButton { border: 1px solid #5D5D5D; border-radius: 16px; "
                                    "background-color: #5D5D5D;}"
                                    "QPushButton::hover { border-radius: 16px; background-color : #2B2B2B;}")
        self.exit_btn.setToolTip("Exit without adding nodes. Hotkey: ESC")

        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems(self.CATEGORY)

        self.instant_search_field = QLineEdit()
        self.instant_search_field.setPlaceholderText("Filter by Node")  # DEFAULT FILTER: Node

        self.graph_selected_btn = QPushButton("Graph Selected")
        self.graph_all_btn = QPushButton(f"Graph All ( {len(self.node_info)} )")

        #########################
        #   BUILD THE TABLE
        #########################
        self.model = QStandardItemModel(len(self.node_info), 1)
        self.model.setHorizontalHeaderLabels(self.CATEGORY)

        self.populate_table()

        self.filter_proxy_model = QSortFilterProxyModel()
        self.filter_proxy_model.setSourceModel(self.model)
        self.filter_proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.filter_proxy_model.setFilterKeyColumn(0)  # DEFAULT SEARCH COLUMN: Node

        self.table = QTableView(self)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.setStyleSheet('QTableView::item {padding-right: 8px;}')
        self.table.setModel(self.filter_proxy_model)

    def create_layout(self):
        main_layout = QGridLayout()

        main_layout.addWidget(self.window_label, 0, 0, 1, 6)
        main_layout.addWidget(self.exit_btn, 0, 5, 1, 1)
        main_layout.addWidget(self.filter_type_combo, 1, 0, 1, 1)
        main_layout.addWidget(self.instant_search_field, 1, 1, 1, 5)
        main_layout.addWidget(self.graph_selected_btn, 2, 0, 1, 3)
        main_layout.addWidget(self.graph_all_btn, 2, 3, 1, 3)
        main_layout.addWidget(self.table, 3, 0, 1, 6)

        self.setLayout(main_layout)

    def create_connections(self):
        self.exit_btn.clicked.connect(self.exit)
        self.instant_search_field.textChanged.connect(self.filter_proxy_model.setFilterRegExp)
        self.filter_type_combo.currentTextChanged.connect(self.on_combo_text_changed)
        self.graph_selected_btn.clicked.connect(self.get_selected_connections)
        self.graph_all_btn.clicked.connect(self.exit)

    #########################
    #   OVERRIDES
    #########################

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.oldPos is not None:
            delta = event.globalPos() - self.oldPos
            self.move(self.pos() + delta)
            self.oldPos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.oldPos = None

    def resizeEvent(self, event):
        QMainWindow.resizeEvent(self, event)
        rect = self.rect()  # top left is already at top left
        self.grips[1].move(rect.right() - self.grip_size, 0)  # top right
        self.grips[2].move(rect.right() - self.grip_size, rect.bottom() - self.grip_size)  # bottom right
        self.grips[3].move(0, rect.bottom() - self.grip_size)  # bottom left

    #########################
    #   HELPER FUNCTIONS
    #########################
    def get_attr_under_mouse_name(self):
        pass

    def get_connected_node_name(self):
        # Nice name as it displays in the node editor
        pass

    def get_connected_node_type(self):
        pass

    def get_connected_node_attrs(self):
        pass

    def get_selected_connections(self):
        indexes = self.table.selectionModel().selectedRows()
        for index in indexes:
            print(f'Row {index.row()} is selected: {index.data()}')

    def graph_connections(self):
        # TODO: call graph connections for all by default, otherwise graph from get_selected_connections()
        self.exit()

    def populate_table(self, sorting_key=0):
        """
        Populates the table with connected node data and refreshes it sorted by column. Default is sorting by Node name.

        :param sorting_key: (integer) The index used to sort the node info by Node name, Attribute, or Type.
        """
        for row, item in enumerate(sorted(self.node_info, key=lambda x: x[sorting_key])):
            data = QStandardItem(item[0])  # Name
            self.model.setItem(row, 0, data)
            data = QStandardItem(item[1])  # Attribute
            self.model.setItem(row, 1, data)
            data = QStandardItem(item[2])  # Type
            self.model.setItem(row, 2, data)

    def on_combo_text_changed(self, text=""):
        """
        Changes the table and filters the node info by Node name, Attribute, or Type.

        :param text: (str) the text in the combobox
        """
        sys.stdout.write(f"Filtering Nodes by: {text}")
        self.instant_search_field.setPlaceholderText(f"Filter by {text}")
        index = self.CATEGORY.index(f"{text}")  # What's sorted with
        self.populate_table(index)
        self.filter_proxy_model.setFilterKeyColumn(index)

    def exit(self):
        self.close()
        self.deleteLater()


if __name__ == "__main__":

    # noinspection PyBroadException
    try:
        nep_connection_filter.close()
        nep_connection_filter.deleteLater()
    except:
        pass

    nep_connection_filter = NEPConnectionFilter()
    nep_connection_filter.show()
