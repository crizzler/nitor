// A titled group of settings, used for every section on every page so spacing stays consistent.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Pane {
    id: card

    required property string title
    property string subtitle: ""
    default property alias content: body.data

    padding: 16

    background: Rectangle {
        radius: 8
        color: card.palette.alternateBase
        border.width: 1
        border.color: Qt.rgba(card.palette.text.r, card.palette.text.g, card.palette.text.b, 0.12)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            // Sized from the card's own resolved font, which follows the system font. Reading it
            // here keeps this component reusable: it needs no knowledge of the application's
            // view model, and it adapts to whatever font context it is placed in.
            Label {
                text: card.title
                font.bold: true
                font.pointSize: Math.round(card.font.pointSize * 1.15)
            }

            Label {
                Layout.fillWidth: true
                visible: card.subtitle.length > 0
                text: card.subtitle
                wrapMode: Text.WordWrap
                opacity: 0.65
                font.pointSize: Math.round(card.font.pointSize * 0.95)
            }
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 10
        }
    }
}
