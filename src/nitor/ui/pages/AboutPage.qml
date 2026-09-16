// About: what this is, what it is not, and where the source lives.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Page {
    id: page

    required property var app

    ScrollView {
        id: scroller
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: scroller.availableWidth
            spacing: 16

            SectionCard {
                Layout.fillWidth: true
                Layout.margins: 20
                title: page.app.appName + " " + page.app.version
                subtitle: "Simple, reliable control of NZXT LED lighting on Linux without NZXT CAM"

                InfoRow {
                    Layout.fillWidth: true
                    label: "License"
                    value: "MIT"
                }

                InfoRow {
                    Layout.fillWidth: true
                    label: "Repository"
                    value: "https://github.com/crizzler/nitor"
                    selectable: true
                }

                InfoRow {
                    Layout.fillWidth: true
                    label: "Backend"
                    value: page.app.backendSummary
                }

                InfoRow {
                    Layout.fillWidth: true
                    label: "Mode"
                    value: page.app.mockMode ? "Mock device (no hardware is touched)" : "Real hardware"
                }

                RowLayout {
                    spacing: 8

                    Button {
                        text: "Open the repository"
                        onClicked: Qt.openUrlExternally("https://github.com/crizzler/nitor")
                    }
                }
            }

            SectionCard {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.bottomMargin: 20
                title: "Non-affiliation"
                subtitle: "Please read this before reporting a problem to NZXT"

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "This project is not affiliated with, endorsed by or supported by NZXT. " +
                          "NZXT, Kraken and HUE are trademarks of their respective owners and are used " +
                          "here only to describe hardware compatibility.\n\n" +
                          "Nitor talks to supported controllers through liquidctl, which is licensed " +
                          "GPL-3.0-or-later and is run as a separate program."
                }
            }
        }
    }
}
