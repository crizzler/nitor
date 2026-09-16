// What to show when the lighting cannot be reached.
//
// Two situations need completely different actions, so they get different cards: a missing backend
// (install a package) and a permission problem (add a udev rule). Nitor never runs sudo itself and
// never asks for a root password.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Pane {
    id: card

    required property bool backendMissing
    required property string backendSummary
    required property string backendHint
    required property string installCommand
    required property bool permissionDenied
    required property string permissionHint

    signal recheckRequested()
    signal copyRequested(string text)

    visible: backendMissing || permissionDenied
    padding: 16

    background: Rectangle {
        radius: 8
        color: Qt.rgba(0.9, 0.35, 0.2, 0.12)
        border.width: 1
        border.color: Qt.rgba(0.9, 0.35, 0.2, 0.4)
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        Label {
            Layout.fillWidth: true
            text: card.backendMissing ? card.backendSummary : "The controller was found, but Linux denied access to it."
            font.bold: true
            wrapMode: Text.WordWrap
        }

        Label {
            Layout.fillWidth: true
            visible: text.length > 0
            text: card.backendMissing ? card.backendHint : card.permissionHint
            wrapMode: Text.WordWrap
            opacity: 0.85
        }

        Label {
            Layout.fillWidth: true
            visible: card.permissionDenied
            wrapMode: Text.WordWrap
            opacity: 0.85
            text: "The controller needs its udev rule. Installing the liquidctl package provides it. " +
                  "If liquidctl was installed another way, copy 71-liquidctl.rules into " +
                  "/etc/udev/rules.d/ and run: sudo udevadm control --reload-rules && sudo udevadm trigger"
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            visible: card.installCommand.length > 0 && card.backendMissing

            Label {
                Layout.fillWidth: true
                text: card.installCommand
                font.family: "monospace"
                elide: Text.ElideRight
                padding: 6
            }

            Button {
                text: "Copy command"
                onClicked: card.copyRequested(card.installCommand)
            }
        }

        RowLayout {
            spacing: 8

            Button {
                text: "Check again"
                onClicked: card.recheckRequested()
            }

            Label {
                Layout.fillWidth: true
                text: "Nitor will never run sudo for you."
                opacity: 0.6
                font.pointSize: Math.round(Qt.application.font.pointSize * 0.9)
            }
        }
    }
}
