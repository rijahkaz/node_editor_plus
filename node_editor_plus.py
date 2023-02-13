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
            if   event.key() == 16777216: # ESC
                self.item.cancel_update_label()
            elif event.key() == 16777220: # Enter
                self.item.label_text_edit.setVisible(False)
            elif event.key() == 16777221: # Enter Numpad
                self.item.label_text_edit.setVisible(False)
        return False

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
    def __init__(self, label, content_rect):
        super().__init__()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.content_rect = QRectF(-10, -10, content_rect.width()+20, content_rect.height()+20)
        self.bounding_rect = self.content_rect
        #self.bounding_rect.adjust()
        self.set_label(label)
        self.bg_color = QColor(255,255,255,50)

    def set_label(self, label):
        self.label = label
        self.label_rect = QFontMetricsF(QFont()).boundingRect(label)
        self.label_rect.adjust(0, -20, 0, 0)

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
            hi_green = QColor(67, 252, 162, 255)
            pen      = QPen(hi_green, 2)
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
        # closes edit if a click is detected (trying to drag)
        super().mousePressEvent(event)
        if self.label_text_edit:
            if self.label_text_edit.isVisible():
                self.cancel_update_label()

    def drag_update_hack(self):
        children = self.childItems()
        if children:
            for ch in children:
                ch.moveBy(0.000001, 0)

    def mouseMoveEvent(self, event):
        # hack to update connections when dragging
        super().mouseMoveEvent(event)
        self.drag_update_hack()

    def mouseReleaseEvent(self, event):
        # hack to update connections when stop dragging
        super().mouseReleaseEvent(event)
        self.drag_update_hack()


    def set_bg_color(self, *args):
        new_color = QColorDialog.getColor()
        if new_color.isValid():
            new_color.setAlpha(50)
            self.bg_color = new_color
            self.update_label_color()

    def update_label_color(self):
        self.Qlabel.setStyleSheet("QLabel { color : "+self.bg_color.name()+"; }")


    

class NodeEditorPlus():
    node_editor = None

    def ui(self):
        cmds.window(title="Node Editor Plus")
        form = cmds.formLayout()
        p = cmds.scriptedPanel(type="nodeEditorPanel")
        self.node_editor = p+"NodeEditorEd"
        cmds.formLayout(form, edit=True, attachForm=[(p,s,0) for s in ("top","bottom","left","right")])
        cmds.showWindow()
        
        cmds.nodeEditor(self.node_editor, edit=True, keyPressCommand=self.comment_key_callback)

    def comment_key_callback(self, *args):
        ''' Detects keypresses'''
        node_editor = args[0]
        key_pressed = args[1]
        # create comment on selected nodes
        if key_pressed == "C":
            self.create_comment_on_selection()
        # rename selected comment
        elif key_pressed == "F2":
            self.rename_comment()
        # change background color for selected comment(s)
        elif key_pressed == "B":
            self.color_comment()


    def color_comment(self):
        scene = getCurrentView(self.node_editor)
        if scene:
            sel = scene.selectedItems()
            if sel:
                for item in sel:
                    if type(item) == NEPComment:
                        item.set_bg_color()


    def rename_comment(self):
        scene = getCurrentView(self.node_editor)
        if scene:
            sel = scene.selectedItems()
            if sel:
                # only rename 1 at a time
                if len(sel) == 1:
                    if type(sel[0]) == NEPComment:
                        sel[0].show_rename_edit_line()



    def create_comment_on_selection(self):
        scene = getCurrentView(self.node_editor)
        if scene:
            sel = scene.selectedItems()
            if sel:
                items_list = []
                for item in sel:
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
                        com = NEPComment("This is a new comment", final_rect)
                        scene.addItem(com)
                        com.setPos( final_rect.x(), final_rect.y() )
                        
                        # parent them to new comment
                        for item in items_list:
                            old_pos = item.scenePos()
                            item.setParentItem(com)
                            item.setPos( com.sceneTransform().inverted()[0].map(old_pos) )
                            
                            # test to see if we can store info inside the nodes
                            item.my_parent = com.label

#nep = NodeEditorPlus()
#nep.ui()