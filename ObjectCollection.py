from PyQt4.QtCore import QModelIndex
from FlatCAMObj import *
import inspect  # TODO: Remove
import FlatCAMApp
from PyQt4 import Qt, QtGui, QtCore


class ObjectCollection(QtCore.QAbstractListModel):

    classdict = {
        "gerber": FlatCAMGerber,
        "excellon": FlatCAMExcellon,
        "cncjob": FlatCAMCNCjob,
        "geometry": FlatCAMGeometry
    }

    icon_files = {
        "gerber": "share/flatcam_icon16.png",
        "excellon": "share/drill16.png",
        "cncjob": "share/cnc16.png",
        "geometry": "share/geometry16.png"
    }

    def __init__(self, parent=None):
        QtCore.QAbstractListModel.__init__(self, parent=parent)
        ### Icons for the list view
        self.icons = {}
        for kind in ObjectCollection.icon_files:
            self.icons[kind] = QtGui.QPixmap(ObjectCollection.icon_files[kind])

        self.object_list = []

        self.view = QtGui.QListView()
        self.view.setModel(self)
        self.view.selectionModel().selectionChanged.connect(self.on_list_selection_change)
        self.view.activated.connect(self.on_item_activated)

    def rowCount(self, parent=QtCore.QModelIndex(), *args, **kwargs):
        return len(self.object_list)

    def columnCount(self, *args, **kwargs):
        return 1

    def data(self, index, role=Qt.Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < self.rowCount():
            return QtCore.QVariant()
        row = index.row()
        if role == Qt.Qt.DisplayRole:
            return self.object_list[row].options["name"]
        if role == Qt.Qt.DecorationRole:
            return self.icons[self.object_list[row].kind]

    def print_list(self):
        for obj in self.object_list:
            print obj

    def append(self, obj, active=False):
        FlatCAMApp.App.log.debug(str(inspect.stack()[1][3]) + " --> OC.append()")

        obj.set_ui(obj.ui_type())

        # Required before appending
        self.beginInsertRows(QtCore.QModelIndex(), len(self.object_list), len(self.object_list))

        self.object_list.append(obj)

        # Required after appending
        self.endInsertRows()

    def get_names(self):
        """
        Gets a list of the names of all objects in the collection.

        :return: List of names.
        :rtype: list
        """

        FlatCAMApp.App.log.debug(str(inspect.stack()[1][3]) + " --> OC.get_names()")
        return [x.options['name'] for x in self.object_list]

    def get_bounds(self):
        """
        Finds coordinates bounding all objects in the collection.

        :return: [xmin, ymin, xmax, ymax]
        :rtype: list
        """
        FlatCAMApp.App.log.debug(str(inspect.stack()[1][3]) + "--> OC.get_bounds()")

        # TODO: Move the operation out of here.

        xmin = Inf
        ymin = Inf
        xmax = -Inf
        ymax = -Inf

        for obj in self.object_list:
            try:
                gxmin, gymin, gxmax, gymax = obj.bounds()
                xmin = min([xmin, gxmin])
                ymin = min([ymin, gymin])
                xmax = max([xmax, gxmax])
                ymax = max([ymax, gymax])
            except:
                FlatCAMApp.App.log.warning("DEV WARNING: Tried to get bounds of empty geometry.")

        return [xmin, ymin, xmax, ymax]

    def get_by_name(self, name):
        """
        Fetches the FlatCAMObj with the given `name`.

        :param name: The name of the object.
        :type name: str
        :return: The requested object or None if no such object.
        :rtype: FlatCAMObj or None
        """
        FlatCAMApp.App.log.debug(str(inspect.stack()[1][3]) + "--> OC.get_by_name()")

        for obj in self.object_list:
            if obj.options['name'] == name:
                return obj
        return None

    def delete_active(self):
        selections = self.view.selectedIndexes()
        if len(selections) == 0:
            return
        row = selections[0].row()

        self.beginRemoveRows(QtCore.QModelIndex(), row, row)

        self.object_list.pop(row)

        self.endRemoveRows()

    def get_active(self):
        selections = self.view.selectedIndexes()
        if len(selections) == 0:
            return None
        row = selections[0].row()
        return self.object_list[row]

    def set_active(self, name):
        iobj = self.createIndex(self.get_names().index(name))
        self.view.selectionModel().select(iobj, QtGui.QItemSelectionModel)

    def on_list_selection_change(self, current, previous):
        FlatCAMApp.App.log.debug("on_list_selection_change()")
        FlatCAMApp.App.log.debug("Current: %s, Previous %s" % (str(current), str(previous)))
        try:
            selection_index = current.indexes()[0].row()
        except IndexError:
            FlatCAMApp.App.log.debug("on_list_selection_change(): Index Error (Nothing selected?)")
            return

        self.object_list[selection_index].build_ui()

    def on_item_activated(self, index):
        self.object_list[index.row()].build_ui()

    def delete_all(self):
        FlatCAMApp.App.log.debug(str(inspect.stack()[1][3]) + "--> OC.delete_all()")

        self.beginResetModel()

        self.object_list = []

        self.endResetModel()

    def get_list(self):
        return self.object_list

