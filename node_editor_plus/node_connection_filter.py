import sys

from PySide2 import QtCore, QtWidgets, QtGui
from shiboken2 import wrapInstance

import maya.OpenMayaUI as omui


def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)


class NEPConnectionFilter(QtWidgets.QDialog):

    def __init__(self, parent=maya_main_window()):
        super(NEPConnectionFilter, self).__init__(parent)

        # TODO: Title is Incoming or Outgoing Connections of NodeName: Attribute
        self.setWindowTitle("Node Name: Attribute I or O")
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)

        self.setMinimumSize(320, 600)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.setModal(True)

        self.CATEGORY = ["Name", "Attributes", "Type"]

        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        connected_nodes = ["node1_postfix", "node2", "node3", "transform1", "nice", "prefix_ok", "ok_postfix",
                           "this is a very very very long name"]
        model = QtGui.QStandardItemModel(len(connected_nodes), 1)
        model.setHorizontalHeaderLabels(self.CATEGORY)  # TODO: Header Depending on I or O

        for row, node in enumerate(sorted(connected_nodes)):
            item = QtGui.QStandardItem(node)
            model.setItem(row, 0, item)

        self.filter_proxy_model = QtCore.QSortFilterProxyModel()
        self.filter_proxy_model.setSourceModel(model)
        self.filter_proxy_model.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.filter_proxy_model.setFilterKeyColumn(0)

        self.instant_search_field = QtWidgets.QLineEdit()
        self.instant_search_field.setPlaceholderText("Filter by Name")  # DEFAULT

        self.graph_selected_btn = QtWidgets.QPushButton("Graph Selected")
        self.graph_all_btn = QtWidgets.QPushButton(f"Graph All ( {len(connected_nodes)} )")

        self.table = QtWidgets.QTableView()
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setModel(self.filter_proxy_model)
        self.table.setStyleSheet('QTableView::item {padding-right: 12px;}')

        self.filter_type_cb = QtWidgets.QComboBox()
        self.filter_type_cb.addItems(self.CATEGORY)

        self.size_grip = QtWidgets.QSizeGrip(self)

    def create_layout(self):
        main_layout = QtWidgets.QGridLayout(self)
        main_layout.addWidget(self.filter_type_cb, 0, 0, 1, 1)
        main_layout.addWidget(self.instant_search_field, 0, 1, 1, 5)
        main_layout.addWidget(self.graph_selected_btn, 1, 0, 1, 3)
        main_layout.addWidget(self.graph_all_btn, 1, 3, 1, 3)
        main_layout.addWidget(self.table, 2, 0, 1, 6)
        main_layout.addWidget(self.size_grip, 3, 0, 1, 6)
        self.setLayout(main_layout)

    def create_connections(self):
        self.instant_search_field.textChanged.connect(self.filter_proxy_model.setFilterRegExp)
        self.filter_type_cb.currentTextChanged.connect(self.on_current_text_changed)

    #########################n
    #   HELPER FUNCTIONS
    #########################

    def get_node_names(self):
        pass

    def get_node_type(self):
        pass

    def get_node_attr(self):
        pass

    def graph_nodes(self):  # TODO: Add Rijah's code :)
        pass

    def on_current_text_changed(self, text):
        print(f"Filtering Nodes by: {text}")
        self.instant_search_field.setPlaceholderText(f"Filter by {text}")


if __name__ == "__main__":

    try:
        nep_connection_filter.close()
        nep_connection_filter.deleteLater()
    except:
        pass

    nep_connection_filter = NEPConnectionFilter()
    nep_connection_filter.show()
