import QtQuick

Rectangle {
    id: scene
    width: 960
    height: 360
    color: "#dbc5b5"
    property font trueTypeFont
    property font cffFont
    property font emojiFont
    property bool reverse: false
    property color ink: "#804979a7"
    property var roles: reverse ? [1, 2, 0, 0, 1, 3, 4] : [0, 0, 1, 2, 0, 3, 4]
    property real glyphOpacity: 0.75
    Repeater {
        model: 2
        delegate: Rectangle {
            required property int index
            x: 0; y: index * 180
            width: 960; height: 180
            color: scene.color
            layer.enabled: index === 1
            Repeater {
                model: scene.roles
                delegate: Item {
                    required property int index
                    required property int modelData
                    x: index * 132; y: 20
                    width: 128; height: 100
                    objectName: "region/" + parent.index + "/" + index
                    property int role: modelData
                    Text {
                        x: 10; y: 10
                        text: parent.role === 2 ? "😀" : "m n o g W V"
                        font: parent.role === 0 ? scene.trueTypeFont : parent.role === 2 ? scene.emojiFont : scene.cffFont
                        color: scene.ink
                        opacity: scene.glyphOpacity
                        Component.onCompleted: {
                            if (parent.role < 3) renderType = Text.NativeRendering
                            else if (parent.role === 3) renderType = Text.QtRendering
                        }
                    }
                    Rectangle { x: 10; y: 46; width: 107; height: 18; color: "#43759b"; opacity: 0.37 }
                    Rectangle { x: 10; y: 74; width: 107; height: 18; color: "#c6813d" }
                }
            }
        }
    }
}
