// The one-line status indicator: what just happened, in normal language.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: pill

    required property string message
    required property color textColor
    property string kind: "idle"

    spacing: 8

    Rectangle {
        width: 9
        height: 9
        radius: 5
        Layout.alignment: Qt.AlignVCenter
        color: {
            switch (pill.kind) {
            case "ok":
                return "#2ecc71";
            case "applying":
                return "#f9c74f";
            case "warning":
                return "#f8961e";
            case "error":
                return "#e63946";
            default:
                return Qt.rgba(pill.textColor.r, pill.textColor.g, pill.textColor.b, 0.35);
            }
        }

        SequentialAnimation on opacity {
            running: pill.kind === "applying"
            loops: Animation.Infinite
            NumberAnimation { to: 0.3; duration: 500 }
            NumberAnimation { to: 1.0; duration: 500 }
        }
    }

    Label {
        text: pill.message
        color: pill.textColor
        elide: Text.ElideRight
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignVCenter
    }
}
