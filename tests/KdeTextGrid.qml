import QtQuick
import org.kde.breeze as Breeze
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

Rectangle {
    id: grid
    width: 760
    height: 370
    property font testFont: Qt.font({family: "Noto Sans", pixelSize: 15})
    property color ink: "black"
    property color paper: "white"
    property real phase: 0
    property real glyphOpacity: 1
    color: paper
    property var names: ["Native Text", "Qt Text", "Default Text", "Breeze Label", "Plasma Label", "Breeze Button"]
    property var letters: ["l", "m", "n", "o", "g", "W", "V", "w", "v"]
    function describe() {
        const found = []
        function walk(item, name) {
            if (item.objectName.startsWith("cell/")) name = item.objectName
            if (name && item.renderType !== undefined && item.text !== undefined) {
                found.push({cell: name, text: item.text, renderType: item.renderType, family: item.font.family,
                            pixels: item.font.pixelSize, origin: item.mapToItem(grid, 0, 0)})
            }
            for (let child of item.children) walk(child, name)
        }
        walk(grid, "")
        return {screenScale: Screen.devicePixelRatio, items: found}
    }
    Repeater {
        model: 6
        delegate: Item {
            id: line
            required property int index
            width: grid.width
            height: 56
            y: 16 + index * 56
            Text { x: 4; y: 17; text: grid.names[line.index]; color: grid.ink; font.family: grid.testFont.family; font.styleName: grid.testFont.styleName; font.pixelSize: 12 }
            Repeater {
                model: grid.letters
                delegate: Rectangle {
                    id: cell
                    required property int index
                    required property string modelData
                    objectName: "cell/" + line.index + "/" + index
                    property string character: modelData
                    property int path: line.index
                    x: 122 + index * 68
                    width: 64
                    height: 52
                    color: grid.paper
                    Loader {
                        opacity: grid.glyphOpacity
                        x: 18 + grid.phase / Screen.devicePixelRatio
                        y: 12
                        width: 40
                        height: 32
                        sourceComponent: [nativeText, qtText, defaultText, breezeLabel, plasmaLabel, breezeButton][line.index]
                        onLoaded: {
                            item.text = cell.character
                            item.font = grid.testFont
                            item.objectName = "glyph"
                        }
                    }
                }
            }
        }
    }
    Component { id: nativeText; Text { color: grid.ink; renderType: Text.NativeRendering } }
    Component { id: qtText; Text { color: grid.ink; renderType: Text.QtRendering } }
    Component { id: defaultText; Text { color: grid.ink } }
    Component { id: breezeLabel; Breeze.Label { color: grid.ink } }
    Component { id: plasmaLabel; PlasmaComponents.Label { color: grid.ink } }
    Component {
        id: breezeButton
        Breeze.Button {
            padding: 0
            Kirigami.Theme.inherit: false
            Kirigami.Theme.textColor: grid.ink
            background: Rectangle { color: grid.paper }
        }
    }
}
