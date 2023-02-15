from maya import cmds, OpenMayaUI
from shiboken2 import wrapInstance
from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *

def getCurrentView(node_editor):
    ctrl = OpenMayaUI.MQtUtil.findControl(node_editor)
    if ctrl is None:
        raise RuntimeError("Node editor is not open")
    nodeEdPane = wrapInstance(int(ctrl), QWidget)
    stack = nodeEdPane.findChild(QStackedLayout)
    graph_view = stack.currentWidget().findChild(QGraphicsView)
    scene = graph_view.scene()
    return scene

class RenameLabelFilter(QObject):
    def __init__(self, item):
        super().__init__()
        self.item = item

    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.KeyPress:
            if   event.key() == Qt.Key_Escape:
                self.item.cancel_update_label()
            elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self.item.label_text_edit.setVisible(False)

        return False

class AlignNodes():
    def __init__(self):
        pass

    def getFullLength(self, axis, graphicsList):
        fullLength = 0
        for node in graphicsList:
            if axis == "x":
                fullLength = fullLength + node.boundingRect().width()
            elif axis == "y":
                fullLength = fullLength + node.boundingRect().height()
    
        return fullLength

    def getInitialNodeValue(self, axis, graphicsList):
        initialValue = 0
        firstNode = graphicsList[0]
        if axis == "x":
            initialValue = firstNode.pos().x()
        elif axis == "y":
            initialValue = firstNode.pos().y()
    
        return initialValue
    
    def horizontalAlign(self, graphicsList):
        xValue = 0
        yValue = 0
        #Get Y Value: Will be the same for all.
        yValue = self.getInitialNodeValue("y", graphicsList)
        #Get full length of nodes selected.
        fLen = self.getFullLength("x", graphicsList)
        #Get gap between Nodes.
        spaceBetween = fLen / len(graphicsList) - 1
        #Get X position for the first node.
        xValue = self.getInitialNodeValue("x", graphicsList)
        #Ititate through list and asign values.
        for node in graphicsList:
            node.setPos(xValue, yValue)
            #Here I add the width because I want a wider gap between them horizontal
            xValue += node.boundingRect().width() + spaceBetween 
    def verticalAlign(self, graphicsList):
        xValue = 0
        yValue = 0
        #Get X Value: Will be the same for all.
        xValue = self.getInitialNodeValue("x", graphicsList)
        #Get full length of nodes selected.
        fLen = self.getFullLength("y", graphicsList)
        #Get gap between Nodes.
        spaceBetween = fLen / len(graphicsList) - 1
        #Get Y position for the first node.
        yValue = self.getInitialNodeValue("y", graphicsList)
        for node in graphicsList:
            node.setPos(xValue, yValue)
            #Here I did not add the height because they would be too far apart.
            yValue += spaceBetween
       

class LabelFilter(QObject):
    def __init__(self, item):
        super().__init__()
        self.item = item

    def eventFilter(self, widget, event):
        if event.type() == QEvent.MouseButtonDblClick:
            self.item.show_rename_edit_line()
        return False

class NEPComment(QGraphicsItem):
    label_rect = None
    label  = ""
    Qlabel = None
    content_rect    = None
    label_text_edit = None
    bounding_rect   = None # full bounds
    is_pinned = False
    pin_icon_off = None
    pin_icon_on  = None
    COLOR_DEFAULT  = QColor(255,255,255,50)
    COLOR_SELECTED = QColor(67, 252, 162, 255)
    temp_item_list = []
    def __init__(self, label, content_rect):
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.content_rect = QRectF(-10, -10, content_rect.width()+20, content_rect.height()+20)
        self.bounding_rect = self.content_rect
        self.set_label(label)

        self.pin_icon_off = QIcon(":/pinItem.png")
        self.pin_icon_on  = QIcon(":/pinON.png")
        self.create_pin()

        self.bg_color = self.COLOR_DEFAULT

    def add_child(self, item):
        # On start drag, parents and fixes position of overlapping nodes
        old_pos = item.scenePos()
        item.setParentItem(self)
        item.setPos(self.sceneTransform().inverted()[0].map(old_pos))

    def remove_child(self, item):
        # On stop drag, unparents and fixes position of child nodes
        scene = self.scene()
        old_pos = item.scenePos()
        self.temp_item_list.append(item) # hack to avoid item to be deleted, seems to work
        item.setParentItem( None )
        #scene.addItem(item)
        item.setPos( old_pos )

    def delete(self):
        scene = self.scene()
        scene.removeItem(self)

    def toggle_pin(self):
        if self.is_pinned:
            self.is_pinned = False
            self.pin_button.setIcon(self.pin_icon_off)
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        else:
            self.is_pinned = True
            self.pin_button.setIcon(self.pin_icon_on)
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

    def create_pin(self):
        self.pin_button = QToolButton()
        self.pin_button.setFixedSize(24,24)
        self.pin_button.setIcon(self.pin_icon_off)
        self.pin_button.setIconSize(QSize(20,20))
        self.pin_button.setAttribute(Qt.WA_NoSystemBackground)
        self.pin_button.released.connect(self.toggle_pin)
        self.is_pinned = False

        pxy = QGraphicsProxyWidget(self)
        pxy.setWidget( self.pin_button )
        pxy.setPos( self.label_rect.x()-24, self.label_rect.y() )

    def set_label(self, label):
        self.label = label
        self.label_rect = QFontMetricsF(QFont()).boundingRect(label)
        self.label_rect.adjust(15, -20, 0, 0)

        if not self.Qlabel:
            self.Qlabel = QLabel(self.label)
            self._labelFilter = LabelFilter(self)
            self.Qlabel.installEventFilter(self._labelFilter)
            self.Qlabel.setAttribute(Qt.WA_NoSystemBackground)
            pxy = QGraphicsProxyWidget(self)
            pxy.setWidget( self.Qlabel )
            pxy.setPos( self.label_rect.x(), self.label_rect.y() )
        else:
            self.Qlabel.setText(self.label)
        
    def boundingRect(self):
        return self.bounding_rect

    def paint(self, painter, option, widget):
        if self.isSelected():
            pen      = QPen(self.COLOR_SELECTED, 2)
        else:
            pen      = QPen(Qt.black, 2)

        path = QPainterPath()
        path.addRoundedRect(self.content_rect, 20, 20)
        
        painter.setPen(pen)
        painter.fillPath(path, self.bg_color )
        painter.drawPath(path)

    def show_rename_edit_line(self):
        if not self.label_text_edit:
            self.label_text_edit = QLineEdit(self.label)
            self.label_text_edit.editingFinished.connect(self.update_label)
            self._renameLabelFilter = RenameLabelFilter(self)
            self.label_text_edit.installEventFilter(self._renameLabelFilter)
            pxy = QGraphicsProxyWidget(self)
            pxy.setWidget( self.label_text_edit )

            pxy.setPos( self.label_rect.x(), self.label_rect.y() )
        else:
            self.label_text_edit.setVisible(True)
        self.Qlabel.setVisible(False)

        self.label_text_edit.setFixedWidth( max(min(self.label_rect.width(), 500), 150) )
        self.label_text_edit.selectAll()
        self.label_text_edit.setFocus()
        self._old_label = self.label_text_edit.text()
        
    def cancel_update_label(self):
        self.label_text_edit.setText(self._old_label)
        self.label_text_edit.setVisible(False)
        self.Qlabel.setVisible(True)

    def update_label(self, *args):
        new_label = self.label_text_edit.text()
        if new_label:
            self.set_label( new_label )
            self.label_text_edit.setVisible(False)
            self.Qlabel.setVisible(True)

    def mousePressEvent(self, event):
        ''' Start dragging - check overlapping nodes and parent to itself.
        Ignores if node is pinned.
        '''
        # closes edit if a click is detected (trying to drag)
        super().mousePressEvent(event)
        if self.label_text_edit:
            if self.label_text_edit.isVisible():
                self.cancel_update_label()

        if self.is_pinned: return

        children = self.childItems() # cache
        colliding_items = self.collidingItems()
        if colliding_items:
            for item in colliding_items:
                if type(item) == QGraphicsItem:
                    if item not in children:
                        if not bool(item.flags() & QGraphicsItem.ItemIsFocusable): # skip searchbox
                            self.add_child(item)


    def drag_update_hack(self):
        children = self.childItems()
        if children:
            for ch in children:
                ch.moveBy(0.000001, 0)

    def mouseMoveEvent(self, event):
        ''' Dragging code - hack to update connections when dragging
        Ignores if node is pinned.
        '''
        super().mouseMoveEvent(event)
        if self.is_pinned: return
        
        self.drag_update_hack()

    def mouseReleaseEvent(self, event):
        ''' Dragging code - hack to update connections when dragging
        Ignores if node is pinned.
        '''
        super().mouseReleaseEvent(event)
        if self.is_pinned: return

        
        self.drag_update_hack()

        children = self.childItems()
        if children:
            # hack to refresh C++ objects everytime children count change
            # so we're not pointing to objects that got deleted
            while True:
                children = self.childItems()
                can_exit = True
                for item in children:
                    if type(item) == QGraphicsItem:
                        self.remove_child(item)
                        can_exit = False
                        break
                if can_exit:
                    break

    def set_bg_color(self, *args):
        new_color = QColorDialog.getColor()
        if new_color.isValid():
            new_color.setAlpha(50)
            self.bg_color = new_color
            self.update_label_color(new_color)

    def update_label_color(self, QColor):
        self.Qlabel.setStyleSheet("QLabel { color : "+QColor.name()+"; }")

    def itemChange(self, change, value):
        # tracks select status
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value:
                self.update_label_color(self.COLOR_SELECTED)
            else:
                self.update_label_color(self.bg_color)

        return QGraphicsItem.itemChange(self, change, value)


    

class NodeEditorPlus():
    node_editor = None

    def ui(self):
        cmds.window(title="Node Editor Plus")
        form = cmds.formLayout()
        p = cmds.scriptedPanel(type="nodeEditorPanel")
        self.node_editor = p+"NodeEditorEd"
        print (self.node_editor)
        cmds.formLayout(form, edit=True, attachForm=[(p,s,0) for s in ("top","bottom","left","right")])
        cmds.showWindow()
        
        cmds.nodeEditor(self.node_editor, edit=True, keyPressCommand=self.comment_key_callback)

    def comment_key_callback(self, *args):
        ''' Detects keypresses'''
        node_editor = args[0]
        key_pressed = args[1]
        mods = cmds.getModifiers()
        # create comment on selected nodes
        if key_pressed == "C":
            self.create_comment_on_selection()
        # rename selected comment
        elif key_pressed == "F2":
            self.rename_comment()
        # change background color for selected comment(s)
        elif key_pressed == "B":
            self.color_comment()
        # delete selected comment(s)
        elif key_pressed == "Del" or key_pressed == "Backspace": 
            self.delete_comment()
        # align selected node(s) horizontally
        elif (mods & 1) > 0 and key_pressed == "A": 
            self.align_nodes("horizontal")
            return True
        # align selected node(s) vertically
        elif (mods & 1) > 0 and key_pressed == "V": 
           self.align_nodes("vertical")
           return True
        print(key_pressed)

    def align_nodes(self, alignIn):
        nodeAl = AlignNodes()
        if alignIn == "vertical":
            #print(nodeAl, alignIn)
            nodeAl.verticalAlign(self.get_selected_comments())
            cmds.nodeEditor( self.node_editor, edit=True, frameAll=True)
        if alignIn == "horizontal":
            #print(nodeAl, alignIn)
            nodeAl.horizontalAlign(self.get_selected_comments())
            cmds.nodeEditor( self.node_editor, edit=True, frameAll=True)


    def get_selected_comments(self):
        selected_items = []
        scene = getCurrentView(self.node_editor)
        if scene:
            sel = scene.selectedItems()
            if sel:
                selected_items = sel
        return selected_items

    def color_comment(self):
        for item in self.get_selected_comments():
            if type(item) == NEPComment:
                item.set_bg_color()

    def rename_comment(self):
        selected_items = self.get_selected_comments()
        if selected_items:
            # only rename 1 at a time
            if len(selected_items) == 1:
                if type(selected_items[0]) == NEPComment:
                    selected_items[0].show_rename_edit_line()

    def delete_comment(self):
        for item in self.get_selected_comments():
            if type(item) == NEPComment:
                item.delete()

    def create_comment_on_selection(self):
        selected_items = self.get_selected_comments()
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
                    com   = NEPComment("This is a new comment", final_rect)
                    scene = getCurrentView(self.node_editor)
                    scene.addItem(com)
                    com.setPos( final_rect.x(), final_rect.y() )


#nep = NodeEditorPlus()
#nep.ui()