import sys
from functools import partial
from shiboken2 import wrapInstance
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from maya import mel, cmds, OpenMayaUI


def maya_main_window():
    main_window_ptr = OpenMayaUI.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QWidget)


def getCurrentScene(node_editor):
    ctrl = OpenMayaUI.MQtUtil.findControl(node_editor)
    if ctrl is None:
        raise RuntimeError("Node editor is not open")
    nodeEdPane = wrapInstance(int(ctrl), QWidget)
    stack = nodeEdPane.findChild(QStackedLayout)
    graph_view = stack.currentWidget().findChild(QGraphicsView)
    scene = graph_view.scene()
    return scene


class NEPConnectionFilter(QDialog):
    """
    Pop-up window to filter and select connections.
    For now only outputs meet the criteria for filter.
    Maybe future update can check all inputs to a node, not just a node's attributes?
    TODO: Option for NO unit conversion nodes?
    """

    def __init__(self, NEP=None, plug="plug", conn_type="output", conn_nodes=[], node_editor=None,
                 parent=maya_main_window()):
        super(NEPConnectionFilter, self).__init__(parent)

        clean_list = [*set(conn_nodes)]     # No duplicate node names (node-attr pairs make duplicate names)
        self.old_pos = None                 # Mouse position before resizing window is stored here
        self.node_editor = node_editor
        self.node_info = []
        self.CATEGORY = ("Node", "Attribute", "Type")
        self.NEP = NEP
        self.PLUG_NAME = plug
        self.SELECTION = clean_list
        self.CONNECTION_TYPE = conn_type
        self.NODES_LIST = clean_list

        mouse_pos = QCursor.pos()
        initial_width = 382
        initial_height = 300

        self.setMinimumSize(initial_height, initial_width)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setModal(True)
        self.setGeometry(mouse_pos.x() + 20, mouse_pos.y() - (initial_height / 2), initial_width, initial_height)

        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        self.grips = []      # Corner resizing grips
        self.grip_size = 8
        for i in range(4):
            grip = QSizeGrip(self)
            grip.resize(self.grip_size, self.grip_size)
            self.grips.append(grip)

        self.window_label = QLabel(f"{self.PLUG_NAME} {self.CONNECTION_TYPE}s")
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
        self.graph_all_btn = QPushButton(f"Graph All ( {len(self.NODES_LIST)} )")

        #########################
        #   BUILD THE TABLE
        #########################
        self.node_info = self.get_connected_node_info()
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
        self.graph_selected_btn.clicked.connect(self.graph_selected_nodes)
        self.graph_all_btn.clicked.connect(self.graph_all_nodes)

    #########################
    #   OVERRIDES
    #########################

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def resizeEvent(self, event):
        QMainWindow.resizeEvent(self, event)
        rect = self.rect()  # top left is already at top left
        self.grips[1].move(rect.right() - self.grip_size, 0)  # top right
        self.grips[2].move(rect.right() - self.grip_size, rect.bottom() - self.grip_size)  # bottom right
        self.grips[3].move(0, rect.bottom() - self.grip_size)  # bottom left

    #########################
    #   HELPER FUNCTIONS
    #########################
    def get_connected_node_info(self):
        sorted_nodes = sorted(self.NODES_LIST)
        node_attrs_loose = sorted(cmds.listConnections(self.PLUG_NAME, plugs=True, destination=True, source=False))
        node_attrs = []
        node_types = [cmds.nodeType(x) for x in sorted_nodes]

        for node_name in sorted_nodes:
            # Get all matching node_name from a list [node_name.attrName1, node_name.attrName2...]
            matching_node_attrs = [x for x in node_attrs_loose if node_name in x]
            # Remove the node name, leaving only the attribute name
            for attr in matching_node_attrs:
                index = matching_node_attrs.index(attr)
                matching_node_attrs[index] = attr.split(".", 1)[1]
            # Make those attribute names a single string separated by newline
            node_attr_string = "\n".join(matching_node_attrs)
            # Add to the node attrs list
            node_attrs.append(node_attr_string)

        node_info = set(zip(sorted_nodes, node_attrs, node_types))
        return node_info

    def populate_table(self, sorting_key=0):
        """
        Populates the table with connected node data and refreshes it sorted by column. Default is sorting by Node name.
        :param sorting_key: (integer) The index used to sort the node info by [Node, Attribute, Type].
        """
        for row, item in enumerate(sorted(self.node_info, key=lambda x: x[sorting_key])):
            data = QStandardItem(item[0])   # Name
            self.model.setItem(row, 0, data)
            data = QStandardItem(item[1])   # Attribute
            self.model.setItem(row, 1, data)
            data = QStandardItem(item[2])   # Type
            self.model.setItem(row, 2, data)

    def on_combo_text_changed(self, text=""):
        """
        Changes the table and filters the node info by Node name, Attribute, or Type.

        :param text: (str) the text in the combobox
        """
        sys.stdout.write(f"Filtering Nodes by: {text}\n")
        self.instant_search_field.setPlaceholderText(f"Filter by {text}")
        index = self.CATEGORY.index(text)  # What's sorted with
        self.populate_table(index)
        self.filter_proxy_model.setFilterKeyColumn(index)

    def graph_selected_nodes(self):
        indexes = self.table.selectionModel().selectedRows()
        if indexes:
            self.SELECTION = []  # Clear main selection
            for index in indexes:
                self.SELECTION.append(index.data())  # collect the Node name from the selected rows
            self.graph_connection()
            self.exit()
        else:
            cmds.warning("Please select the nodes you want to add!")

    def graph_all_nodes(self):
        self.graph_connection()
        self.exit()

    def graph_connection(self):
        cmds.select(clear=True)
        cmds.select(self.PLUG_NAME.split('.',1)[0])     # The name of the node pulled from the nodeName.attrName pair

        source_item = self.get_selected_items()[0]

        for node in self.SELECTION:  # first add them to make sure they exist in the graph
            cmds.nodeEditor(self.node_editor, addNode=node, layout=False, edit=True)

        cmds.select(self.SELECTION)  # now grab their items
        cmds.refresh(force=True)
        QTimer.singleShot(100, partial(self.graph_connection_organize, source_item))

    def graph_connection_organize(self, source_item):
        # roughly aligns new added nodes to the source_item
        cmds.nodeEditor(self.node_editor, nodeViewMode="connected", edit=True)
        dest_items = self.get_selected_items()

        y_offset = source_item.pos().y()
        for item in dest_items:
            item.setPos(source_item.pos().x() + (item.boundingRect().width()) * 1.5, y_offset + 20)
            y_offset = +item.pos().y() + item.boundingRect().height()

    def get_selected_items(self):
        selected_items = []
        scene = getCurrentScene(self.node_editor)
        if scene:
            sel = scene.selectedItems()
            if sel:
                selected_items = sel
        return selected_items

    def exit(self):
        self.close()
        self.deleteLater()
