import importlib
from functools import partial
from maya import cmds, mel

def override_clear_function(node_editor):
    # to check if the current graph has our custom nodes
    new_cmd = '''global proc nodeEdClearAll(string $ned)
                {
                    if ($ned != "")
                    {
                        int $execute = 0;
                        python("from node_editor_plus import node_editor_plus");
                        python("import importlib; importlib.reload(node_editor_plus)");
                        if (`python("node_editor_plus.NodeEditorPlus.is_graph_extended(\\"'''+node_editor+'''\\")")`)
                        {
                            if (`python("node_editor_plus.NodeEditorPlus.is_graph_suppressed()")` == 1) {
                                python("node_editor_plus.NodeEditorPlus.clear_graph(\\"'''+node_editor+'''\\")");
                                $execute = 1;
                            } else {
                                if (`confirmDialog -title "Confirm" -message "There are Comments or Images in the current Tab.\\nAre you sure you want to clear the graph?\\nThis operation is NOT undoable."
                                                        -button "Yes" -button "No" -defaultButton "No"
                                                        -cancelButton "No" -dismissString "No"` == "Yes")
                                {
                                    python("node_editor_plus.NodeEditorPlus.clear_graph(\\"'''+node_editor+'''\\")");
                                    $execute = 1;
                                } else {
                                    $execute = 0;
                                }
                            }
                        } else {
                            $execute = 1;
                        }

                        if ($execute){
                            nodeEditor -e -rootNode "" $ned;
                        }
                    }
                }'''
    mel.eval(new_cmd)

def restore_clear_function():
    # avoid errors if our UI is closed
    old_cmd = '''global proc nodeEdClearAll(string $ned)
                {
                    if ($ned != "") {
                        nodeEditor -e -rootNode "" $ned;
                    }
                }'''
    mel.eval(old_cmd)

def override_remove_function(node_editor):
    new_cmd = '''global proc nodeEdRemoveSelected(string $ned)
                {
                    if ($ned != "") {
                        python("from node_editor_plus import node_editor_plus");
                        python("import importlib; importlib.reload(node_editor_plus)");
                        if (`python("node_editor_plus.NodeEditorPlus.is_graph_extended(\\"'''+node_editor+'''\\")")`)
                        {
                            python("node_editor_plus.NodeEditorPlus.static_delete_item(\\"'''+node_editor+'''\\")");
                        }
                        nodeEditor -e -rem "" $ned;
                    }
                }'''
    mel.eval(new_cmd)

def restore_remove_function():
    old_cmd = '''global proc nodeEdRemoveSelected(string $ned)
                {
                    if ($ned != "") {
                        nodeEditor -e -rem "" $ned;
                    }
                }'''
    mel.eval(old_cmd)

def override_graph_function(node_editor):
    # first check if it's additive mode, if not then we need to clear our stuff so Maya doesn't complain
    # remove our custom nodes from the current selection, if there are still native nodes selected, remove all of ours and fallback to old graph
    new_cmd = '''global proc nodeEdGraph(string $ned, int $upstream, int $downstream)
                {
                    if ($ned != "")
                    {
                        int $execute = 0;
                        if (`nodeEditor -q -additiveGraphingMode $ned`) {
                            $execute = 1;
                        } else {
                            python("from node_editor_plus import node_editor_plus");
                            python("import importlib; importlib.reload(node_editor_plus)");
                            if (`python("node_editor_plus.NodeEditorPlus.is_graph_extended(\\"'''+node_editor+'''\\")")`)
                            {
                                if (`python("node_editor_plus.NodeEditorPlus.clean_selection(\\"'''+node_editor+'''\\")")`)
                                {
                                    if (`python("node_editor_plus.NodeEditorPlus.is_graph_suppressed()")` == 1) {
                                        python("node_editor_plus.NodeEditorPlus.clear_graph(\\"'''+node_editor+'''\\")");
                                        $execute = 1;
                                    } else {
                                        if (`confirmDialog -title "Confirm" -message "There are Comments or Images in the current Tab.\\nGraphing will delete them, are you sure?\\nThis operation is NOT undoable."
                                                        -button "Yes" -button "No" -defaultButton "No"
                                                        -cancelButton "No" -dismissString "No"` == "Yes")
                                        {
                                            python("node_editor_plus.NodeEditorPlus.clear_graph(\\"'''+node_editor+'''\\")");
                                            $execute = 1;
                                        } else {
                                            $execute = 0;
                                        }
                                    }
                                } else {
                                    python("node_editor_plus.NodeEditorPlus.static_show_message(\\"'''+node_editor+'''\\", \\"Cannot graph Comment or Image nodes\\", 0, 3)");
                                    $execute = 0;
                                }
                            } else {
                                $execute = 1;
                            }
                        }

                        if ($execute){
                            if ($upstream && $downstream) {
                                nodeEdGraphControl($ned, "nodeEditor -e -rfs -ups -ds ");
                            } else if ($upstream) {
                                nodeEdGraphControl($ned, "nodeEditor -e -rfs -ups ");
                            } else if ($downstream) {
                                nodeEdGraphControl($ned, "nodeEditor -e -rfs -ds ");
                            }
                        }
                    }
                }'''
    mel.eval(new_cmd)

def restore_graph_function():
    old_cmd = '''global proc nodeEdGraph(string $ned, int $upstream, int $downstream)
                {
                    if ($ned != "") {
                        if ($upstream && $downstream) {
                            nodeEdGraphControl($ned, "nodeEditor -e -rfs -ups -ds ");
                        } else if ($upstream) {
                            nodeEdGraphControl($ned, "nodeEditor -e -rfs -ups ");
                        } else if ($downstream) {
                            nodeEdGraphControl($ned, "nodeEditor -e -rfs -ds ");
                        }
                    }
                }'''
    mel.eval(old_cmd)

def decorate_bookmarks_functions(NEP):
    # adds decorators to handle our custom nodes when bookmarks get loaded or saved
    def handle_save_decor(function):
        def wrapper(*args, **kwargs):
            # make sure code is pointing to right editor
            args_list = list(args)
            args_list[0] = NEP.node_editor

            # same hack original window uses to get new info
            n0 = set(cmds.ls(type='nodeGraphEditorBookmarkInfo'))
            output = function(*args_list, **kwargs) # run original function
            n1 = set(cmds.ls(type='nodeGraphEditorBookmarkInfo'))
            newInfos = n1 - n0
            if len(newInfos):
                newInfo = newInfos.pop()
                NEP.save_nep_data_to_bookmark(newInfo)
            return output
        return wrapper

    def handle_load_decor(function):
        def wrapper(*args, **kwargs):
            # first we confirm if the user really wants to clear the graph, if so, deletes our custom nodes first so Maya doesn't crash
            from node_editor_plus import node_editor_plus
            importlib.reload(node_editor_plus)
            execute = False
            if node_editor_plus.NodeEditorPlus.is_graph_extended(NEP.node_editor):
                if node_editor_plus.NodeEditorPlus.is_graph_suppressed() == "1":
                    execute = True
                else:
                    if cmds.confirmDialog( title="Confirm", message="There are Comments or Images in the current Tab.\nLoading a bookmark will delete them, are you sure?\nThis operation is NOT undoable.", button=["Yes","No"], defaultButton="No", cancelButton="No", dismissString="No") == "Yes":
                        execute = True
                    else:
                        execute = False
            else:
                execute = True

            if execute:
                node_editor_plus.NodeEditorPlus.clear_graph(NEP.node_editor)
                # make sure code is pointing to right editor
                args_list = list(args)
                args_list[0] = NEP.node_editor
                output = function(*args_list, **kwargs) # run original function
                NEP.load_nep_data_from_bookmark(args_list[1])
                return output
        return wrapper

    def handle_replace_decor(function):
        def wrapper(*args, **kwargs):
            output = function(*args, **kwargs) # run original function
            # same code as original but saving our stuff
            txt = cmds.textScrollList(args[0]._tsl, query=True, selectItem=True)
            if txt and len(txt):
                txt = txt[0]
                info = args[0]._findInfo(txt)
                bookmark_name = cmds.getAttr(info + ".name")
                NEP.save_nep_data_to_bookmark(bookmark_name)
            return output
        return wrapper

    import maya.app.general.nodeEditorBookmarks
    importlib.reload(maya.app.general.nodeEditorBookmarks)
    maya.app.general.nodeEditorBookmarks.createBookmark = handle_save_decor(maya.app.general.nodeEditorBookmarks.createBookmark)
    maya.app.general.nodeEditorBookmarks.loadBookmark   = handle_load_decor(maya.app.general.nodeEditorBookmarks.loadBookmark)
    maya.app.general.nodeEditorBookmarks.NodeEditorBookmarksWindow._onReplace = handle_replace_decor(maya.app.general.nodeEditorBookmarks.NodeEditorBookmarksWindow._onReplace)

    # fix initial bookmarks, I guess this function is never called the way we create the editor
    maya.app.general.nodeEditorBookmarks.addCallback(NEP.node_editor)

def restore_bookmarks_functions():
    import maya.app.general.nodeEditorBookmarks
    importlib.reload(maya.app.general.nodeEditorBookmarks)

def add_extra_option(NEP):
    # find menu
    options_menu = None
    for menu in cmds.lsUI(menus=True):
        menu_label = cmds.menu(menu, query=True, label=True)
        menu_items = cmds.menu(menu, query=True, itemArray=True)
        if "Options" in menu_label and menu_items:
            if NEP.node_editor+"RSI" in menu_items:
                options_menu = menu
                break

    supress_mi = NEP.node_editor+"NEPSCD" #Node Editor Plus Supress Confirm Dialogs
    if options_menu:
        if not supress_mi in menu_items:
            cmds.menuItem( label="Node Editor Plus: Supress Confirm Dialogs", checkBox=False, parent=options_menu, command=partial(NEP.suppress_checkbox_toggled, supress_mi) )
