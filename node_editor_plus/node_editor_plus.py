import os, json, base64, importlib
from functools import partial
from collections import OrderedDict
from maya import mel, cmds, OpenMayaUI
from shiboken2 import wrapInstance
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *
from node_editor_plus import custom_nodes
from node_editor_plus import overrides

# version tracking
VERSION = "0.1.27"

# constants
WINDOW_NAME = "NodeEditorPlusWindow"
DEFAULT_HUD_MESSAGE = "Press Tab to create a node"
NODE_EDITOR_CFG = "MayaNodeEditorPlusSavedTabsInfo"

def getCurrentScene(node_editor):
    ctrl = OpenMayaUI.MQtUtil.findControl(node_editor)
    if ctrl is None:
        raise RuntimeError("Node editor is not open")
    nodeEdPane = wrapInstance(int(ctrl), QWidget)
    stack = nodeEdPane.findChild(QStackedLayout)
    graph_view = stack.currentWidget().findChild(QGraphicsView)
    scene = graph_view.scene()
    return scene

def getCurrentView(node_editor):
    scene = getCurrentScene(node_editor)
    return scene.views()[0]

       
class NEPMousePosFilter(QObject):
    # tracks mouse position on certain actions like graphing in/out connections
    def __init__(self, NEP):
        super().__init__()
        self._NEP = NEP

    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.GraphicsSceneMouseMove:
            self._NEP.mouse_pos = event.scenePos()
        return False

class NodeEditorPlus():
    node_editor = None
    icons_path = ""
    _drag_manager = None
    _mouse_pos_filter = None
    mouse_pos = None
    grid_snap = False
    def __init__(self):
        # manager to propagate drags between our custom nodes
        self._drag_manager = custom_nodes.NEPDragManager()
        self.aligner = custom_nodes.NEPNodeAligner()
        self.icons_path = os.path.join(os.path.dirname(__file__), "icons")
        self.initialize_suppress_file_info()

    def tab_change_callback(self):
        """ force new tabs to also recognize our hotkeys, this is weird since there is only 1 node editor
        but hotkeys only work in the first tab otherwise """
        cmds.nodeEditor(self.node_editor, edit=True, keyPressCommand=self.comment_key_callback)

        # intercept for our needs then call original callback
        parent   = cmds.setParent(query=True)
        showMenu = None # this doesn't seem it's being used at all in the function
        mel.eval("nodeEdUpdateUIByTab \"{}\" \"{}\"".format(self.node_editor, showMenu))

    def settings_changed_callback(self, *args):
        # intercept for our needs then call original callback
        #print(cmds.nodeEditor(self.node_editor, query=True, stateString=True))
        self.grid_snap = cmds.nodeEditor(self.node_editor, query=True, gridSnap=True)
        mel.eval("nodeEdSyncControls \"{}\"".format(args[0]))

    def close_all_node_editors(self, debug=False):
        # makes sure only our Node Editor Plus window is shown otherwise Tabs break
        windows_list = cmds.lsUI(windows=True)
        for window in windows_list:
            if "nodeEditorPanel" in window:
                cmds.deleteUI(window)
        if cmds.window(WINDOW_NAME, exists=True):
            if debug:
                cmds.deleteUI(WINDOW_NAME)
                return False
            else:
                cmds.showWindow(WINDOW_NAME)
                return True
        return False

    def ui(self, debug=False):
        if self.close_all_node_editors(debug):
            return

        cmds.window(WINDOW_NAME, title="Node Editor Plus v{}".format(VERSION), widthHeight=(800, 550), closeCommand=self.window_close )
        form = cmds.formLayout()
        p = cmds.scriptedPanel(type="nodeEditorPanel")
        self.node_editor = p+"NodeEditorEd"
        cmds.formLayout(form, edit=True, attachForm=[(p,s,0) for s in ("top","bottom","left","right")])

        # our upgrade to the Node Editor :3
        self.create_sidebar()

        # this never worked, I'm disabling it
        cmds.nodeEditor(self.node_editor, edit=True, allowTabTearoff=False)
        # intercept hotkeys for our functionality
        cmds.nodeEditor(self.node_editor, edit=True, keyPressCommand=self.comment_key_callback)
        # in case we need to intercept these too, but atm it's not doing anything (v0.1.4)
        cmds.nodeEditor(self.node_editor, edit=True, tabChangeCommand=self.tab_change_callback)
        # intercept original callbacks, there are important so we can apply grid snapping for example
        cmds.nodeEditor(self.node_editor, edit=True, settingsChangedCallback=self.settings_changed_callback)

        cmds.showWindow(WINDOW_NAME)

        # optimize images on launch
        self.optimize_images_data()
        # hack to not crash Maya, check for other ways
        QTimer.singleShot(500, self.load_nep_data_from_scene)
        #print(self.node_editor)

        # tracks mouse position on certain actions like graphing in/out connections
        # UNUSED (as of v0.1.15)
        self._mouse_pos_filter = NEPMousePosFilter(self)
        scene = getCurrentScene(self.node_editor)
        scene.installEventFilter(self._mouse_pos_filter)

        # change a couple things of the original graph to keep ours more stable
        overrides.override_clear_function(self.node_editor)
        overrides.override_remove_function(self.node_editor)
        overrides.override_graph_function(self.node_editor)
        overrides.decorate_bookmarks_functions(self)
        overrides.add_extra_option(self)

    def initialize_suppress_file_info(self):
        # creates it as false if not existing when editor launches
        val = cmds.fileInfo("NEP_suppress_confirm_dialogs", query=True)
        if not val:
            cmds.fileInfo("NEP_suppress_confirm_dialogs", 0)

    def suppress_checkbox_toggled(self, *args):
        if args[1]:
            val = 1
        else:
            val = 0
        cmds.fileInfo('NEP_suppress_confirm_dialogs', val)

    @staticmethod
    def is_graph_suppressed():
        return cmds.fileInfo("NEP_suppress_confirm_dialogs", query=True)[0]

    @staticmethod
    def is_graph_extended(ned=None):
        # checks if we have our custom nodes in the provided graph
        return_value = False
        scene = getCurrentScene(ned)
        if scene:
            scene_items = scene.items()
            if scene_items:
                for item in scene_items:
                    if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                        return_value = True
                        break
        return return_value

    @staticmethod
    def clean_selection(ned=None):
        '''removes our nodes from the selection to see if there are native nodes left, used by graphing
        returns False if no nodes are left
        '''
        scene = getCurrentScene(ned)
        clean_selected_items = []
        if scene:
            selected_items = scene.selectedItems()
            if selected_items:
                for item in selected_items:
                    if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                        item.setSelected(False)

            # no selected custom items
            if not scene.selectedItems():
                # but are there Maya nodes selected?
                if cmds.ls(sl=True):
                    return True
                else:
                    return False
            else:
                return True
    @staticmethod
    def static_show_message(ned=None, message=None, message_type=0, duration=3):
        cmds.nodeEditor(ned, edit=True, hudMessage=[message, message_type, duration])

    @staticmethod
    def clear_graph(ned=None):
        # clean clear procedure so we don't crash Maya
        scene = getCurrentScene(ned)
        if scene:
            scene_items = scene.items()
            if scene_items:
                for item in scene_items:
                    if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                        item.delete()


    def comment_key_callback(self, *args):
        ''' Detects keypresses'''
        node_editor = args[0]
        key_pressed = args[1]

        mods = cmds.getModifiers()
        #print(key_pressed, "mods:", mods)
        
        # create comment on selected nodes
        if key_pressed == "C":
            self.create_comment()
            return True
        # rename selected comment
        elif key_pressed == "F2":
            self.rename_comment()
            return True
        # change background color for selected comment(s)
        elif key_pressed == "B":
            self.color_comment()
            return True
        # add image
        elif mods == 4 and key_pressed == "I":
            self.pick_new_image()
            return True
        # search comments
        elif mods == 4 and key_pressed == "F":
            self.show_search_menu()
            return True
        # graph input connection
        elif key_pressed == "I":
            self.graph_connection("input")
            return True
        elif key_pressed == "O":
            self.graph_connection("output")
            return True
        # delete selected comment(s)
        elif key_pressed == "Del" or key_pressed == "Backspace": 
            self.delete_item()
        # align selected node(s) to the Middle
        elif mods == 9 and key_pressed == "W": 
            self.alignNodes("middle")
            return True
        # align selected node(s) to the Center
        elif mods == 9 and key_pressed == "S": 
            self.alignNodes("center")
            return True
        # align selected node(s) to the Top
        elif mods == 1 and key_pressed == "W": 
            self.alignNodes("top")
            return True
        # align selected node(s) to the Bottom
        elif mods == 1 and key_pressed == "S": 
            self.alignNodes("bottom")
            return True
        # align selected node(s) to the Left
        elif mods == 1 and key_pressed == "A": 
            self.alignNodes("left")
            return True
        # align selected node(s) to the Right
        elif mods == 1 and key_pressed == "D": 
            self.alignNodes("right")
            return True
        # distribute selected node(s) Horizontally
        elif mods == 1 and key_pressed == "H": 
            self.alignNodes("horizontal")
            return True
        # distribute selected node(s) Vertically
        elif mods == 1 and key_pressed == "V": 
           self.alignNodes("vertical")
           return True

        # remake of original hotkeys to make them work with our custom nodes
        # ToDo: make them calculate our nodes to frame 
        elif key_pressed == "A":
            cmds.nodeEditor(node_editor, edit=True, frameAll=True)
            return True
        elif key_pressed == "F":
            cmds.nodeEditor(node_editor, edit=True, frameSelected=True)
            return True
        # in the end if we didn't intercept a key, run original callback
        return mel.eval("nodeEdKeyPressCommand \"{}\" \"{}\"".format(node_editor, key_pressed))

    def toolbar_add_button(self, toolbar, tooltip, icon_name, command):
        if not icon_name.startswith(":"):
            a = QAction(icon=QIcon(os.path.join(self.icons_path, icon_name)), text="", parent=toolbar)
        else:
            a = QAction(icon=QIcon(icon_name), text="", parent=toolbar)
        a.setToolTip(tooltip) # hovering tooltip
        a.setStatusTip("Node Editor Plus: {}".format(tooltip)) # Maya's help line description
        a.triggered.connect(command)
        toolbar.addAction(a)

    def create_sidebar(self):
        # Reparents old NodeEditor into a new horizontal layout so we can add a sidebar to the window
        ctrl = OpenMayaUI.MQtUtil.findControl(self.node_editor)
        nodeEdPane = wrapInstance(int(ctrl), QWidget)
        nodeEdPaneParent = nodeEdPane.parent().parent().objectName()
        parent_ctrl = OpenMayaUI.MQtUtil.findControl(nodeEdPaneParent)
        original_widget = wrapInstance(int(parent_ctrl), QWidget)
        original_layout = original_widget.layout()
        alignNode = False

        # create our new layout and add it
        self.horizontal_main_layout = QHBoxLayout()
        original_layout.insertLayout( 0, self.horizontal_main_layout )

        # create the left side toolbar 
        self.left_toolbar = QToolBar()
        self.left_toolbar.setOrientation(Qt.Vertical)

        # comments buttons
        self.left_toolbar.addSeparator()
        self.toolbar_add_button(self.left_toolbar, "Create New Comment (C)",      "comment_add.svg",    self.create_comment)
        self.toolbar_add_button(self.left_toolbar, "Delete Item (Del)",           "comment_remove.svg", self.delete_item)
        self.toolbar_add_button(self.left_toolbar, "Change Comment Color (B)",    "comment_color.svg",  self.color_comment)
        self.toolbar_add_button(self.left_toolbar, "Add Image to Graph (Ctrl+I)", "image_add.svg",      self.pick_new_image)
        self.toolbar_add_button(self.left_toolbar, "Search Comments (Ctrl+F)",    ":/search.png",       self.show_search_menu)
        
        # align buttons
        self.left_toolbar.addSeparator()
        self.toolbar_add_button(self.left_toolbar, "Align Top (Shift+W)",         "align_top.svg",    partial(self.alignNodes,"top"))
        self.toolbar_add_button(self.left_toolbar, "Align Middle (Alt+Shift+W)",  "align_middle.svg", partial(self.alignNodes,"middle"))
        self.toolbar_add_button(self.left_toolbar, "Align Bottom (Shift+S)",      "align_bottom.svg", partial(self.alignNodes,"bottom"))
        self.toolbar_add_button(self.left_toolbar, "Align Left (Shift+A)",        "align_left.svg",   partial(self.alignNodes,"left"))
        self.toolbar_add_button(self.left_toolbar, "Align Center (Alt+Shift+S)",  "align_center.svg", partial(self.alignNodes,"center"))
        self.toolbar_add_button(self.left_toolbar, "Align Right (Shift+D)",       "align_right.svg",  partial(self.alignNodes,"right"))
        self.toolbar_add_button(self.left_toolbar, "Distribute Horizontally (Shift+H)", "distribute_horizontal.svg", partial(self.alignNodes,"horizontal"))
        self.toolbar_add_button(self.left_toolbar, "Distribute Vertically (Shift+V)",   "distribute_vertical.svg",   partial(self.alignNodes,"vertical"))
        self.left_toolbar.addSeparator()


        # add the populated toolbar to the new layout we created
        self.horizontal_main_layout.addWidget(self.left_toolbar)

        # re-add the Node Editor to our new layout
        ctrl = OpenMayaUI.MQtUtil.findControl(self.node_editor)
        nodeEdPane = wrapInstance(int(ctrl), QWidget)
        alignNode = True
        self.horizontal_main_layout.addWidget(nodeEdPane)


    def show_search_menu(self):
        scene = getCurrentScene(self.node_editor)
        comments_list = []
        if scene:
            scene_items = scene.items()
            for item in scene_items:
                if type(item) == custom_nodes.NEPComment:
                    comments_list.append(item)

        self.search_box = custom_nodes.show_NEPSearchBox(NEP=self, comments_list=comments_list, parent=self.left_toolbar)

    def focus_item(self, item):
        # called by the search menu
        view = getCurrentView(self.node_editor)
        view.resetTransform() # resets zoom level to default
        view.centerOn(item)

    def alignNodes(self, alignIn):
        selected_items = self.get_selected_items()
        if not selected_items:
            print("No nodes selected")
            return

        if alignIn == "top":
            self.aligner.topAlign(selected_items)
        elif alignIn == "middle":
            self.aligner.middleAlign(selected_items)
        elif alignIn == "bottom":
            self.aligner.bottomAlign(selected_items)
        elif alignIn == "left":
            self.aligner.leftAlign(selected_items)
        elif alignIn == "center":
            self.aligner.centerAlign(selected_items)
        elif alignIn == "right":
            self.aligner.rightAlign(selected_items)
        elif alignIn == "horizontal":
            self.aligner.horizontalDistribute(selected_items)
        elif alignIn == "vertical":
            self.aligner.verticalDistribute(selected_items)

    def hide_default_HUD_message(self):
        cmds.nodeEditor(self.node_editor, edit=True, hudMessage=("", 3, 0))

    def get_selected_items(self):
        selected_items = []
        scene = getCurrentScene(self.node_editor)
        if scene:
            sel = scene.selectedItems()
            if sel:
                selected_items = sel
        return selected_items

    def color_comment(self):
        selected_items = self.get_selected_items()
        if selected_items:
            valid_comment_nodes = []
            for item in selected_items:
                if type(item) == custom_nodes.NEPComment:
                    valid_comment_nodes.append(item)

            if valid_comment_nodes:
                new_color = QColorDialog.getColor()
                for item in valid_comment_nodes:
                    item.set_bg_color(new_color)

    def rename_comment(self):
        selected_items = self.get_selected_items()
        if selected_items:
            # only rename 1 at a time
            if len(selected_items) == 1:
                if type(selected_items[0]) == custom_nodes.NEPComment:
                    selected_items[0].show_rename_edit_line()

    def delete_item(self, items_list=None):
        if not items_list:
            items_list = self.get_selected_items()

        for item in items_list:
            if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                item.delete()

        # at the end if nothing is left in scene, show the default HUD message
        scene = getCurrentScene(self.node_editor)
        if not scene.items():
            cmds.nodeEditor(self.node_editor, edit=True, hudMessage=(DEFAULT_HUD_MESSAGE, 3, 0))

    @staticmethod
    def static_delete_item(ned):
        scene = getCurrentScene(ned)
        if scene:
            selected_items = scene.selectedItems()
            if selected_items:
                for item in selected_items:
                    if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                        item.delete()

    def create_comment(self):
        scene = getCurrentScene(self.node_editor)
        selected_items = self.get_selected_items()
        if selected_items:
            items_list = []
            for item in selected_items:
                if type(item) == QGraphicsItem:
                    items_list.append(item)
            if items_list:
                final_rect = None
                for item in items_list:
                    if not final_rect:
                        final_rect = item.sceneBoundingRect()
                    else:
                        final_rect = final_rect.united(item.sceneBoundingRect())
                if final_rect:
                    com   = custom_nodes.NEPComment("", final_rect, self)
                    scene.addItem(com)
                    com.setPos( final_rect.x(), final_rect.y() )
        else:
            # if nothing selected and no items in scene, remove the default HUD message
            if not scene.items():
                self.hide_default_HUD_message()
            default_rect = QRectF(0, 0, 150, 50)
            com   = custom_nodes.NEPComment("", default_rect, self)
            scene.addItem(com)
            view = getCurrentView(self.node_editor)
            center = view.mapToScene(view.viewport().rect().center())
            com.setPos( center.x()-75, center.y()-25 )

    def pick_new_image(self):
        image_path = QFileDialog.getOpenFileName(parent=None, caption='Please select an image file', filter="*.png")
        if not image_path[0]:
            return

        try:
            encoded_image = None
            with open(image_path[0], 'rb') as image_file:
                encoded_image = base64.b64encode(image_file.read())

            if encoded_image:
                attr_name = "IMG_LIST"
                create_dict = self.create_nep_data(create_string_array_attr=attr_name)
                if create_dict["created_attr"]:
                    old_array = []
                    size = 0
                else:
                    old_array = cmds.getAttr(NODE_EDITOR_CFG+"."+attr_name)
                    size = len(old_array)
                new_array = old_array + [encoded_image]
                
                cmds.setAttr(NODE_EDITOR_CFG+"."+attr_name, size+1, *new_array, type="stringArray")

                self.create_image(encoded_image=encoded_image, img_index=size)
        except:
            cmds.error("Could not load image: {}".format(image_path[0]))

    def create_image(self, encoded_image, img_index):
        scene = getCurrentScene(self.node_editor)
        # if nothing selected and no items in scene, remove the default HUD message
        if not scene.items():
            self.hide_default_HUD_message()

        img   = custom_nodes.NEPImage(label="", content_rect=None, NEP=self, encoded_image=encoded_image)
        img.set_img_index(img_index)
        scene.addItem(img)
        view = getCurrentView(self.node_editor)
        center = view.mapToScene(view.viewport().rect().center())
        img.setPos( center.x()-75, center.y()-25 )

    def get_not_found_encoded_img(self):
        image_path = os.path.join(os.path.dirname(__file__), "img/not_found.png")
        with open(image_path, 'rb') as image_file:
            return base64.b64encode(image_file.read())

    def optimize_images_data(self):
        # checks all images being used in the scene, clear binary data of unused indices
        attr_name = "NEP_DATA"
        used_indices = []
        if cmds.objExists(NODE_EDITOR_CFG): # only do this if we have a CFG node, otherwise there are no images stored in the scene
            if cmds.attributeQuery("IMG_LIST", node=NODE_EDITOR_CFG, exists=True):
                if cmds.attributeQuery(attr_name, node=NODE_EDITOR_CFG, exists=True):
                    load_dict = json.loads(cmds.getAttr(NODE_EDITOR_CFG+"."+attr_name))

                    for tab_name in load_dict:
                        for item in load_dict[tab_name]:
                            if item["nep_type"] == "image":
                                if not item["img_index"] in used_indices:
                                    used_indices.append(item["img_index"])

                bookmark_infos = cmds.ls(type='nodeGraphEditorBookmarkInfo')
                if bookmark_infos:
                    for info_node in bookmark_infos:
                        if cmds.attributeQuery(attr_name, node=info_node, exists=True):
                            load_dict = json.loads(cmds.getAttr(info_node+"."+attr_name))
                            for item in load_dict["bookmark"]:
                                if item["nep_type"] == "image":
                                    if not item["img_index"] in used_indices:
                                        used_indices.append(item["img_index"])

                img_array = cmds.getAttr(NODE_EDITOR_CFG+".IMG_LIST")
                size = len(img_array)
                for i in range(size):
                    if i not in used_indices:
                        img_array[i] = "" # clear what was there

                cmds.setAttr(NODE_EDITOR_CFG+".IMG_LIST", size, *img_array, type="stringArray")


    def graph_connection(self, conn_type="output"):
        plug_under_cursor = cmds.nodeEditor(self.node_editor, feedbackPlug=True, query=True)
        if plug_under_cursor:
            con_nodes = []
            if conn_type == "input":
                con_nodes = cmds.listConnections(plug_under_cursor, source=True, destination=False, skipConversionNodes=False)
            elif conn_type == "output":
                con_nodes = cmds.listConnections(plug_under_cursor, source=False, destination=True, skipConversionNodes=False)
            
            if con_nodes:
                source_node = cmds.nodeEditor(self.node_editor, feedbackNode=True, query=True)
                cmds.nodeEditor(self.node_editor, selectNode="", edit=True) # clear
                cmds.nodeEditor(self.node_editor, selectNode=source_node, edit=True)

                source_item = self.get_selected_items()[0]

                # first add them to make sure they exist in the graph
                for node in con_nodes:
                    cmds.nodeEditor(self.node_editor, addNode=node, layout=False, edit=True)

                # now grab their items
                cmds.select(con_nodes)
                cmds.refresh(force=True)
                QTimer.singleShot(100, partial(self.graph_connection_organize, source_item, conn_type))

    def graph_connection_organize(self, source_item, conn_type):
        # roughly aligns new added nodes to the source_item
        cmds.nodeEditor(self.node_editor, nodeViewMode="connected", edit=True)
        dest_items = self.get_selected_items()

        # "inputs" align to the left
        if conn_type == "input":
            y_offset = source_item.pos().y()
            for item in dest_items:
                item.setPos( source_item.pos().x()-(item.boundingRect().width())*1.5, y_offset+20 )
                y_offset = item.pos().y() + item.boundingRect().height()

        # "outputs" align to the right
        elif conn_type == "output":
            y_offset = source_item.pos().y()
            for item in dest_items:
                item.setPos( source_item.pos().x()+(item.boundingRect().width())*1.5, y_offset+20 )
                y_offset = +item.pos().y() + item.boundingRect().height()


    def window_close(self):
        # avoid errors if user launches original Node Editor
        overrides.restore_clear_function()
        overrides.restore_remove_function()
        overrides.restore_graph_function()
        overrides.restore_bookmarks_functions()

        # custom nodes persistence
        self.save_nep_data_to_scene()

    def create_nep_data(self, create_string_attr=None, create_string_array_attr=None):
        return_dict = {"created_node":False, "created_attr":False}
        if not cmds.objExists(NODE_EDITOR_CFG):
            cmds.createNode("network", name=NODE_EDITOR_CFG)
            cmds.lockNode(NODE_EDITOR_CFG, lock=True) # please don't delete me
            return_dict["created_node"] = True

        if create_string_attr:
            if not cmds.attributeQuery(create_string_attr, node=NODE_EDITOR_CFG, exists=True):
                cmds.lockNode(NODE_EDITOR_CFG, lock=False)
                cmds.addAttr(NODE_EDITOR_CFG, ln=create_string_attr, dataType="string")
                cmds.lockNode(NODE_EDITOR_CFG, lock=True)
                return_dict["created_attr"] = True
        elif create_string_array_attr:
            if not cmds.attributeQuery(create_string_array_attr, node=NODE_EDITOR_CFG, exists=True):
                cmds.lockNode(NODE_EDITOR_CFG, lock=False)
                cmds.addAttr(NODE_EDITOR_CFG, ln=create_string_array_attr, dataType="stringArray")
                cmds.lockNode(NODE_EDITOR_CFG, lock=True)
                return_dict["created_attr"] = True
        return return_dict

    def save_nep_data_to_bookmark(self, info_node):
        attr_name = "NEP_DATA"
        if cmds.objExists(info_node):
            if not cmds.attributeQuery(attr_name, node=info_node, exists=True):
                cmds.addAttr(info_node, ln=attr_name, dataType="string")

            dump_dict = {}
            dump_dict["bookmark"] = []
            scene = getCurrentScene(self.node_editor)
            items_list = scene.items()
            if items_list:
                for item in items_list:
                    item_type = type(item)
                    if   item_type == custom_nodes.NEPComment:
                        dump_dict["bookmark"].append( {"nep_type":"comment", "label":item.label,         "pos":{"x":item.pos().x(), "y":item.pos().y()}, "width":item.content_rect.width(), "height":item.content_rect.height(), "bg_color":item.bg_color.name(), "is_pinned":item.is_pinned} )
                    elif item_type == custom_nodes.NEPImage:
                        dump_dict["bookmark"].append( {"nep_type":"image",   "img_index":item.img_index, "pos":{"x":item.pos().x(), "y":item.pos().y()}, "width":item.content_rect.width(), "height":item.content_rect.height(), "bg_color":item.bg_color.name(), "is_pinned":item.is_pinned} )
                cmds.setAttr(info_node+"."+attr_name, json.dumps(dump_dict), type="string")

    def load_nep_data_from_bookmark(self, info_node):
        attr_name = "NEP_DATA"
        load_dict = {}
        if cmds.objExists(info_node):
            if cmds.attributeQuery(attr_name, node=info_node, exists=True):
                nep_data = cmds.getAttr(info_node+"."+attr_name)
                if nep_data:
                    load_dict = json.loads(cmds.getAttr(info_node+"."+attr_name))

        if load_dict:
            scene = getCurrentScene(self.node_editor)
            for item in load_dict["bookmark"]:
                if   item["nep_type"] == "comment":
                    nep_item = custom_nodes.NEPComment(label=item["label"], content_rect=QRectF(0, 0, item["width"]-20, item["height"]-20), NEP=self, bg_color=item["bg_color"], is_pinned=item["is_pinned"])
                elif item["nep_type"] == "image":
                    if not cmds.objExists(NODE_EDITOR_CFG) or not cmds.attributeQuery("IMG_LIST", node=NODE_EDITOR_CFG, exists=True):
                        encoded_image = self.get_not_found_encoded_img()
                    else:
                        encoded_image = cmds.getAttr(NODE_EDITOR_CFG+".IMG_LIST")[item["img_index"]]
                    nep_item = custom_nodes.NEPImage(label="", encoded_image=encoded_image, content_rect=QRectF(0, 0, item["width"]-20, item["height"]-20), NEP=self, bg_color=item["bg_color"], is_pinned=item["is_pinned"])
                    nep_item.set_img_index(item["img_index"])
                scene.addItem(nep_item)

                if item["nep_type"] == "comment":
                    nep_item.setZValue(-1)
                nep_item.setPos(item["pos"]["x"], item["pos"]["y"])


    def save_nep_data_to_scene(self):
        tabs_dict = OrderedDict()
        tabs_names_list = []

        ctrl = OpenMayaUI.MQtUtil.findControl(self.node_editor)
        if ctrl is None:
            raise RuntimeError("Node editor is not open")
        nodeEdPane = wrapInstance(int(ctrl), QWidget)

        tabbar = nodeEdPane.findChild(QTabBar)
        for i in range(tabbar.count()-1): # removes +
            tabs_names_list.append(tabbar.tabText(i))

        stack = nodeEdPane.findChild(QStackedLayout)
        for i in range(stack.count()):
            children = stack.itemAt(i).widget().children()
            for child in children:
                if type(child) == QGraphicsView:
                    valid_items_list = []
                    for item in child.items():
                        if type(item) in [custom_nodes.NEPComment, custom_nodes.NEPImage]:
                            valid_items_list.append(item)

                    tabs_dict[tabs_names_list[i]] = valid_items_list

        dump_dict = {}
        for tab in tabs_dict:
            dump_dict[tab] = []
            for item in tabs_dict[tab]:
                item_type = type(item)
                if   item_type == custom_nodes.NEPComment:
                    dump_dict[tab].append( {"nep_type":"comment", "label":item.label,         "pos":{"x":item.pos().x(), "y":item.pos().y()}, "width":item.content_rect.width(), "height":item.content_rect.height(), "bg_color":item.bg_color.name(), "is_pinned":item.is_pinned} )
                elif item_type == custom_nodes.NEPImage:
                    dump_dict[tab].append( {"nep_type":"image",   "img_index":item.img_index, "pos":{"x":item.pos().x(), "y":item.pos().y()}, "width":item.content_rect.width(), "height":item.content_rect.height(), "bg_color":item.bg_color.name(), "is_pinned":item.is_pinned} )
                

        self.create_nep_data(create_string_attr="NEP_DATA")
        cmds.setAttr(NODE_EDITOR_CFG+".NEP_DATA", json.dumps(dump_dict), type="string")

    def load_nep_data_from_scene(self):
        load_dict = {}

        if cmds.objExists(NODE_EDITOR_CFG):
            if cmds.attributeQuery("NEP_DATA", node=NODE_EDITOR_CFG, exists=True):
                load_dict = json.loads(cmds.getAttr(NODE_EDITOR_CFG+".NEP_DATA"))
            else:
                return

        ctrl = OpenMayaUI.MQtUtil.findControl(self.node_editor)
        if ctrl is None:
            raise RuntimeError("Node editor is not open")
        nodeEdPane = wrapInstance(int(ctrl), QWidget)

        tabbar = nodeEdPane.findChild(QTabBar)
        stack  = nodeEdPane.findChild(QStackedLayout)
        for i in range(tabbar.count()-1): # removes +
            tab_name = tabbar.tabText(i)
            if tab_name in load_dict:
                stack.setCurrentIndex(i)
                graph_view = stack.currentWidget().findChild(QGraphicsView)
                scene = graph_view.scene()

                for item in load_dict[tab_name]:
                    if   item["nep_type"] == "comment":
                        nep_item = custom_nodes.NEPComment(label=item["label"], content_rect=QRectF(0, 0, item["width"]-20, item["height"]-20), NEP=self, bg_color=item["bg_color"], is_pinned=item["is_pinned"])
                    elif item["nep_type"] == "image":
                        if not cmds.objExists(NODE_EDITOR_CFG) or not cmds.attributeQuery("IMG_LIST", node=NODE_EDITOR_CFG, exists=True):
                            encoded_image = self.get_not_found_encoded_img()
                        else:
                            encoded_image = cmds.getAttr(NODE_EDITOR_CFG+".IMG_LIST")[item["img_index"]]
                        nep_item = custom_nodes.NEPImage(label="", encoded_image=encoded_image, content_rect=QRectF(0, 0, item["width"]-20, item["height"]-20), NEP=self, bg_color=item["bg_color"], is_pinned=item["is_pinned"])
                        nep_item.set_img_index(item["img_index"])
                    scene.addItem(nep_item)

                    if item["nep_type"] == "comment":
                        nep_item.setZValue(-1)
                    nep_item.setPos(item["pos"]["x"], item["pos"]["y"])
