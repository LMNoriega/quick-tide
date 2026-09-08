import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts

Window {
    id: root
    width: 740
    height: 560
    visible: true
    title: "Tidal - Búsqueda"
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.Window

    // Paleta de colores de Serpantinum
    readonly property var theme: backend.theme

    // Modo: "tracks" (Canciones), "albums" (Álbumes) o "playlists" (Playlists)
    property string currentMode: backend.currentMode
    readonly property bool isTrackMode: currentMode === "tracks"
    readonly property bool isAlbumMode: currentMode === "albums"
    readonly property bool isPlaylistMode: currentMode === "playlists"
    readonly property color currentAccent: isPlaylistMode ? theme.blue : (isAlbumMode ? theme.peach : theme.mauve)

    Component.onCompleted: {
        searchInput.forceFocus();
    }

    Connections {
        target: backend
        function onIsDetailViewChanged() {
            if (backend.isDetailView) {
                detailSearchInput.text = "";
                detailSearchInput.forceActiveFocus();
            } else {
                searchInput.forceFocus();
            }
        }
    }

    TextMetrics {
        id: fontMetrics
        font.family: "JetBrains Mono"
        font.pixelSize: 13
        font.bold: true
        text: "0"
    }

    function appendToSearch(chars) {
        innerInput.text += chars;
        innerInput.cursorPosition = innerInput.text.length;
        searchInput.syncChars(innerInput.text);
        backend.playTypeSound();
        backend.search(innerInput.text, root.currentMode);
        innerInput.forceActiveFocus();
    }

    function backspaceSearch() {
        if (innerInput.text.length > 0) {
            innerInput.text = innerInput.text.slice(0, -1);
            innerInput.cursorPosition = innerInput.text.length;
            searchInput.syncChars(innerInput.text);
            backend.playTypeSound();
            backend.search(innerInput.text, root.currentMode);
        }
        innerInput.forceActiveFocus();
    }

    function appendToDetailSearch(chars) {
        detailSearchInput.text += chars;
        detailSearchInput.cursorPosition = detailSearchInput.text.length;
        detailSearchInput.forceActiveFocus();
    }

    function backspaceDetailSearch() {
        if (detailSearchInput.text.length > 0) {
            detailSearchInput.text = detailSearchInput.text.slice(0, -1);
            detailSearchInput.cursorPosition = detailSearchInput.text.length;
        }
        detailSearchInput.forceActiveFocus();
    }

    function handleGlobalKey(event) {
        if (backend.isDetailView) {
            if (detailSearchInput.activeFocus) {
                return;
            }
            if (event.key === Qt.Key_Escape) {
                if (detailSearchInput.text.length > 0) {
                    detailSearchInput.text = "";
                } else {
                    backend.closeDetail();
                    searchInput.forceFocus();
                }
                event.accepted = true;
                return;
            }
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                if (detailTrackList.count > 0 && detailTrackList.currentIndex >= 0) {
                    backend.playFromDetail(detailTrackList.currentIndex);
                    root.close();
                }
                event.accepted = true;
                return;
            }
            if (event.key === Qt.Key_Down) {
                if (detailTrackList.count > 0) {
                    if (detailTrackList.currentIndex < detailTrackList.count - 1) {
                        detailTrackList.currentIndex++;
                    } else {
                        detailTrackList.currentIndex = 0;
                    }
                    detailTrackList.positionViewAtIndex(detailTrackList.currentIndex, ListView.Contain);
                    backend.playSwitchSound();
                }
                event.accepted = true;
                return;
            }
            if (event.key === Qt.Key_Up) {
                if (detailTrackList.count > 0) {
                    if (detailTrackList.currentIndex > 0) {
                        detailTrackList.currentIndex--;
                    } else {
                        detailTrackList.currentIndex = detailTrackList.count - 1;
                    }
                    detailTrackList.positionViewAtIndex(detailTrackList.currentIndex, ListView.Contain);
                    backend.playSwitchSound();
                }
                event.accepted = true;
                return;
            }
            if (event.key === Qt.Key_Backspace) {
                backspaceDetailSearch();
                event.accepted = true;
                return;
            }
            if (event.text && event.text.length > 0 && event.text >= " ") {
                appendToDetailSearch(event.text);
                event.accepted = true;
                return;
            }
        } else {
            if (innerInput.activeFocus) {
                return;
            }
            if (event.key === Qt.Key_Escape) {
                root.close();
                event.accepted = true;
                return;
            }
            if (event.key === Qt.Key_Tab) {
                backend.playSwitchSound();
                let nextMode = "tracks";
                if (root.isTrackMode) nextMode = "albums";
                else if (root.isAlbumMode) nextMode = "playlists";
                else nextMode = "tracks";
                backend.setMode(nextMode, innerInput.text);
                searchInput.forceFocus();
                event.accepted = true;
                return;
            }
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                if (resultsList.count > 0 && resultsList.currentIndex >= 0) {
                    let selected = backend.results[resultsList.currentIndex];
                    if (selected) {
                        backend.playClickSound();
                        if (root.isAlbumMode || root.isPlaylistMode || selected.type === "album" || selected.type === "playlist") {
                            backend.openDetail(selected);
                        } else {
                            backend.playSelection(selected);
                            root.close();
                        }
                    }
                }
                event.accepted = true;
                return;
            }
            if (event.key === Qt.Key_Down) {
                if (resultsList.count > 0) {
                    if (resultsList.currentIndex < resultsList.count - 1) {
                        resultsList.currentIndex++;
                    } else {
                        resultsList.currentIndex = 0;
                    }
                    resultsList.positionViewAtIndex(resultsList.currentIndex, ListView.Contain);
                    backend.playSwitchSound();
                }
                event.accepted = true;
                return;
            }
            if (event.key === Qt.Key_Up) {
                if (resultsList.count > 0) {
                    if (resultsList.currentIndex > 0) {
                        resultsList.currentIndex--;
                    } else {
                        resultsList.currentIndex = resultsList.count - 1;
                    }
                    resultsList.positionViewAtIndex(resultsList.currentIndex, ListView.Contain);
                    backend.playSwitchSound();
                }
                event.accepted = true;
                return;
            }
            if (event.key === Qt.Key_Backspace) {
                backspaceSearch();
                event.accepted = true;
                return;
            }
            if (event.text && event.text.length > 0 && event.text >= " ") {
                appendToSearch(event.text);
                event.accepted = true;
                return;
            }
        }
    }

    // Contenedor principal con efecto de vidrio esmerilado / liquid glass
    Rectangle {
        id: bgContainer
        anchors.fill: parent
        radius: 14
        color: Qt.alpha(theme.base, 0.78)
        border.color: Qt.alpha(currentAccent, 0.55)
        border.width: 1.5
        clip: true
        focus: true

        Keys.onPressed: function(event) {
            handleGlobalKey(event);
        }

        Behavior on border.color {
            ColorAnimation { duration: 250 }
        }
        Behavior on color {
            ColorAnimation { duration: 250 }
        }

        Item {
            id: contentArea
            anchors.fill: parent
            anchors.margins: 18

            // ========================================================
            // VISTA 1: BÚSQUEDA Y LISTADO GENERAL
            // ========================================================
            ColumnLayout {
                id: searchView
                anchors.fill: parent
                spacing: 12
                visible: opacity > 0
                opacity: backend.isDetailView ? 0 : 1
                enabled: !backend.isDetailView

                Behavior on opacity { NumberAnimation { duration: 160 } }

                // ================= HEADER & TABS =================
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 14

                    // Selector de modo con píldora animada (Canciones, Álbumes, Playlists)
                    Rectangle {
                        id: modeToggle
                        Layout.preferredWidth: 320
                        Layout.preferredHeight: 36
                        radius: 10
                        color: Qt.alpha(theme.surface0, 0.65)
                        border.color: Qt.alpha(theme.surface2, 0.70)
                        border.width: 1

                        // Fondo deslizante animado del tab activo
                        Rectangle {
                            id: tabHighlight
                            width: (parent.width - 6) / 3
                            height: parent.height - 6
                            y: 3
                            x: root.isPlaylistMode ? (3 + (parent.width - 6) * 2 / 3) : (root.isAlbumMode ? (3 + (parent.width - 6) / 3) : 3)
                            radius: 8
                            color: Qt.alpha(root.currentAccent, 0.90)

                            Behavior on x {
                                NumberAnimation { duration: 220; easing.type: Easing.OutBack; easing.overshoot: 1.15 }
                            }
                            Behavior on color {
                                ColorAnimation { duration: 220 }
                            }
                        }

                        Row {
                            anchors.fill: parent
                            Item {
                                width: parent.width / 3
                                height: parent.height
                                Text {
                                    anchors.centerIn: parent
                                    text: "🎵 Canciones"
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: root.isTrackMode ? theme.crust : theme.subtext0
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (!root.isTrackMode) {
                                            backend.playSwitchSound();
                                            backend.setMode("tracks", searchInput.inputText);
                                            searchInput.forceFocus();
                                        }
                                    }
                                }
                            }
                            Item {
                                width: parent.width / 3
                                height: parent.height
                                Text {
                                    anchors.centerIn: parent
                                    text: "💿 Álbumes"
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: root.isAlbumMode ? theme.crust : theme.subtext0
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (!root.isAlbumMode) {
                                            backend.playSwitchSound();
                                            backend.setMode("albums", searchInput.inputText);
                                            searchInput.forceFocus();
                                        }
                                    }
                                }
                            }
                            Item {
                                width: parent.width / 3
                                height: parent.height
                                Text {
                                    anchors.centerIn: parent
                                    text: "📑 Playlists"
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: root.isPlaylistMode ? theme.crust : theme.subtext0
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (!root.isPlaylistMode) {
                                            backend.playSwitchSound();
                                            backend.setMode("playlists", searchInput.inputText);
                                            searchInput.forceFocus();
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Subtítulo
                    Column {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: "Tidal Hi-Fi Serpantinum"
                            font.family: "JetBrains Mono"
                            font.pixelSize: 14
                            font.bold: true
                            color: root.currentAccent
                            Behavior on color { ColorAnimation { duration: 200 } }
                        }
                        Text {
                            text: root.isPlaylistMode
                                  ? "Explorar tus playlists y colecciones de Tidal"
                                  : (root.isAlbumMode ? "Explorar y reproducir álbumes completos" : "Búsqueda y reproducción de canciones en alta fidelidad")
                            font.family: "JetBrains Mono"
                            font.pixelSize: 11
                            color: theme.subtext0
                        }
                    }

                    // Indicador de atajos
                    Text {
                        text: "[Tab] Modo • [Esc] Salir"
                        font.family: "JetBrains Mono"
                        font.pixelSize: 11
                        color: theme.subtext1
                    }
                }

                // ================= SEARCH BAR (FROSTED GLASS) =================
                Rectangle {
                    id: searchBarContainer
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    radius: 10
                    color: Qt.alpha(theme.surface0, 0.65)
                    border.width: 1.5
                    border.color: innerInput.activeFocus ? root.currentAccent : Qt.alpha(theme.surface1, 0.70)

                    property real focusPop: 1.0
                    scale: focusPop

                    Behavior on border.color { ColorAnimation { duration: 180 } }
                    Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutQuint } }

                    SequentialAnimation {
                        id: focusPopAnim
                        NumberAnimation { target: searchBarContainer; property: "focusPop"; to: 1.02; duration: 90; easing.type: Easing.OutQuad }
                        NumberAnimation { target: searchBarContainer; property: "focusPop"; to: 1.0; duration: 200; easing.type: Easing.OutQuint }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 8

                        Text {
                            text: root.isPlaylistMode ? "📑" : (root.isAlbumMode ? "💿" : "🔍")
                            font.pixelSize: 14
                            color: innerInput.activeFocus ? root.currentAccent : theme.subtext0
                        }

                        Item {
                            id: searchInput
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true

                            property alias inputText: innerInput.text

                            function forceFocus() {
                                innerInput.forceActiveFocus();
                            }

                            function clear() {
                                innerInput.text = "";
                                charModel.clear();
                                backend.search("", root.currentMode);
                            }

                            function syncChars(newText) {
                                if (newText.length > charModel.count && newText.startsWith(getCurrentModelText())) {
                                    for (let i = charModel.count; i < newText.length; i++) {
                                        charModel.append({ "char": newText[i] });
                                    }
                                } else if (newText.length < charModel.count && getCurrentModelText().startsWith(newText)) {
                                    while (charModel.count > newText.length) {
                                        charModel.remove(charModel.count - 1);
                                    }
                                } else {
                                    charModel.clear();
                                    for (let i = 0; i < newText.length; i++) {
                                        charModel.append({ "char": newText[i] });
                                    }
                                }
                            }

                            function getCurrentModelText() {
                                let str = "";
                                for (let i = 0; i < charModel.count; i++) {
                                    str += charModel.get(i).char;
                                }
                                return str;
                            }

                            // Placeholder
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: root.isPlaylistMode
                                      ? "Buscar playlists en Tidal (o vacía para ver tus playlists)..."
                                      : (root.isAlbumMode
                                         ? "Buscar álbumes en Tidal (ej: Random Access Memories, Starboy)..."
                                         : "Buscar canciones en Tidal (ej: Blinding Lights, Get Lucky)...")
                                font.family: "JetBrains Mono"
                                font.pixelSize: 12
                                color: theme.subtext1
                                opacity: (innerInput.text.length === 0 && charModel.count === 0) ? 0.6 : 0.0
                                Behavior on opacity { NumberAnimation { duration: 140 } }
                            }

                            // Modelo de caracteres
                            ListModel { id: charModel }

                            // Fila de caracteres con animación de entrada (bouncy pop)
                            Row {
                                id: charRow
                                height: parent.height
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 1

                                Repeater {
                                    model: charModel
                                    delegate: Item {
                                        width: Math.max(fontMetrics.width, charText.implicitWidth)
                                        height: charRow.height

                                        Text {
                                            id: charText
                                            anchors.centerIn: parent
                                            text: model.char
                                            font.family: "JetBrains Mono"
                                            font.pixelSize: 13
                                            font.bold: true
                                            color: theme.text
                                            scale: 0.2
                                            y: 8
                                            opacity: 0

                                            ParallelAnimation {
                                                running: true
                                                NumberAnimation { target: charText; property: "scale"; to: 1.0; duration: 280; easing.type: Easing.OutBack; easing.overshoot: 3.2 }
                                                NumberAnimation { target: charText; property: "y"; to: 0; duration: 280; easing.type: Easing.OutBack; easing.overshoot: 2.2 }
                                                NumberAnimation { target: charText; property: "opacity"; to: 1.0; duration: 100 }
                                            }
                                        }
                                    }
                                }
                            }

                            // Cursor deslizante animado
                            Rectangle {
                                id: caretRect
                                width: 2
                                height: 16
                                color: root.currentAccent
                                visible: innerInput.activeFocus
                                anchors.verticalCenter: parent.verticalCenter
                                x: Math.min(innerInput.cursorPosition * (fontMetrics.width + 1) + 2, parent.width - 4)

                                Behavior on x {
                                    NumberAnimation { duration: 160; easing.type: Easing.OutQuad }
                                }
                                Behavior on color {
                                    ColorAnimation { duration: 180 }
                                }

                                SequentialAnimation on opacity {
                                    running: innerInput.activeFocus
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 0; duration: 100; easing.type: Easing.InQuad }
                                    PauseAnimation { duration: 400 }
                                    NumberAnimation { to: 1; duration: 100; easing.type: Easing.OutQuad }
                                    PauseAnimation { duration: 400 }
                                }
                            }

                            // TextInput con el foco permanente
                            TextInput {
                                id: innerInput
                                anchors.fill: parent
                                opacity: 0
                                focus: true

                                onActiveFocusChanged: {
                                    if (activeFocus) focusPopAnim.restart();
                                }

                                onTextEdited: {
                                    searchInput.syncChars(text);
                                    backend.playTypeSound();
                                    backend.search(text, root.currentMode);
                                }

                                Keys.onDownPressed: function(event) {
                                    if (resultsList.count > 0) {
                                        if (resultsList.currentIndex < resultsList.count - 1) {
                                            resultsList.currentIndex++;
                                        } else {
                                            resultsList.currentIndex = 0;
                                        }
                                        resultsList.positionViewAtIndex(resultsList.currentIndex, ListView.Contain);
                                        backend.playSwitchSound();
                                    }
                                    event.accepted = true;
                                }

                                Keys.onUpPressed: function(event) {
                                    if (resultsList.count > 0) {
                                        if (resultsList.currentIndex > 0) {
                                            resultsList.currentIndex--;
                                        } else {
                                            resultsList.currentIndex = resultsList.count - 1;
                                        }
                                        resultsList.positionViewAtIndex(resultsList.currentIndex, ListView.Contain);
                                        backend.playSwitchSound();
                                    }
                                    event.accepted = true;
                                }

                                Keys.onTabPressed: function(event) {
                                    backend.playSwitchSound();
                                    let nextMode = "tracks";
                                    if (root.isTrackMode) nextMode = "albums";
                                    else if (root.isAlbumMode) nextMode = "playlists";
                                    else nextMode = "tracks";

                                    backend.setMode(nextMode, innerInput.text);
                                    searchInput.forceFocus();
                                    event.accepted = true;
                                }

                                Keys.onReturnPressed: function(event) {
                                    if (resultsList.count > 0 && resultsList.currentIndex >= 0) {
                                        let selected = backend.results[resultsList.currentIndex];
                                        if (selected) {
                                            backend.playClickSound();
                                            if (root.isAlbumMode || root.isPlaylistMode || selected.type === "album" || selected.type === "playlist") {
                                                backend.openDetail(selected);
                                            } else {
                                                backend.playSelection(selected);
                                                root.close();
                                            }
                                        }
                                    }
                                    event.accepted = true;
                                }

                                Keys.onEscapePressed: function(event) {
                                    root.close();
                                    event.accepted = true;
                                }
                            }
                        }

                        // Botón de limpiar búsqueda
                        Text {
                            text: "✕"
                            font.pixelSize: 12
                            color: theme.subtext1
                            visible: innerInput.text.length > 0
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    searchInput.clear();
                                    searchInput.forceFocus();
                                }
                            }
                        }
                    }
                }

                // ================= RESULTADOS =================
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 10
                    color: Qt.alpha(theme.surface0, 0.40)
                    border.color: Qt.alpha(theme.surface1, 0.50)
                    border.width: 1
                    clip: true

                    ListView {
                        id: resultsList
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 4
                        clip: true
                        model: backend.results
                        focus: false

                        Keys.onPressed: function(event) {
                            handleGlobalKey(event);
                        }

                        // Barra de selección deslizante animada
                        highlight: Rectangle {
                            radius: 8
                            color: Qt.alpha(root.currentAccent, 0.22)
                            border.color: Qt.alpha(root.currentAccent, 0.70)
                            border.width: 1.2
                            z: 2
                            Behavior on y {
                                NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                            }
                            Behavior on border.color { ColorAnimation { duration: 150 } }
                            Behavior on color { ColorAnimation { duration: 150 } }
                        }
                        highlightFollowsCurrentItem: true
                        highlightMoveDuration: 140

                        delegate: Item {
                            width: resultsList.width
                            height: 56

                            readonly property bool isSelected: ListView.isCurrentItem
                            readonly property var itemData: modelData

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                onEntered: {
                                    resultsList.currentIndex = index;
                                }
                                onClicked: {
                                    resultsList.currentIndex = index;
                                    backend.playClickSound();
                                    if (root.isAlbumMode || root.isPlaylistMode || itemData.type === "album" || itemData.type === "playlist") {
                                        backend.openDetail(itemData);
                                    } else {
                                        backend.playSelection(itemData);
                                        root.close();
                                    }
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 14
                                spacing: 12

                                // Carátula / Icono
                                Rectangle {
                                    Layout.preferredWidth: 42
                                    Layout.preferredHeight: 42
                                    radius: 6
                                    color: Qt.alpha(theme.surface1, 0.8)
                                    border.color: Qt.alpha(theme.surface2, 0.5)
                                    border.width: 1
                                    clip: true

                                    Image {
                                        anchors.fill: parent
                                        source: itemData.cover_url || ""
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        visible: status === Image.Ready
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        text: itemData.type === "playlist" ? "📑" : (itemData.type === "album" ? "💿" : "🎵")
                                        font.pixelSize: 18
                                        visible: !itemData.cover_url || parent.children[0].status !== Image.Ready
                                    }
                                }

                                // Metadatos principales
                                Column {
                                    Layout.fillWidth: true
                                    spacing: 2

                                    Row {
                                        spacing: 6
                                        Text {
                                            text: itemData.name || ""
                                            font.family: "JetBrains Mono"
                                            font.pixelSize: 13
                                            font.bold: true
                                            color: isSelected ? theme.text : theme.subtext0
                                            elide: Text.ElideRight
                                            width: Math.min(implicitWidth, itemData.is_user ? 310 : 380)
                                        }

                                        // Badge si es playlist del usuario
                                        Rectangle {
                                            visible: !!itemData.is_user
                                            width: myPlaylistBadgeText.implicitWidth + 8
                                            height: 16
                                            radius: 4
                                            y: 1
                                            color: Qt.alpha(theme.blue, 0.25)
                                            border.color: theme.blue
                                            border.width: 1
                                            Text {
                                                id: myPlaylistBadgeText
                                                anchors.centerIn: parent
                                                text: "Mi Playlist"
                                                font.family: "JetBrains Mono"
                                                font.pixelSize: 9
                                                font.bold: true
                                                color: theme.blue
                                            }
                                        }

                                        // Badge si es explícito
                                        Rectangle {
                                            visible: !!itemData.explicit
                                            width: 14
                                            height: 14
                                            radius: 3
                                            y: 2
                                            color: Qt.alpha(theme.red, 0.3)
                                            border.color: theme.red
                                            border.width: 1
                                            Text {
                                                anchors.centerIn: parent
                                                text: "E"
                                                font.pixelSize: 9
                                                font.bold: true
                                                color: theme.red
                                            }
                                        }
                                    }

                                    Row {
                                        spacing: 8
                                        Text {
                                            text: (itemData.artist || itemData.creator) || ""
                                            font.family: "JetBrains Mono"
                                            font.pixelSize: 11
                                            font.bold: true
                                            color: isSelected ? root.currentAccent : (itemData.type === "playlist" ? theme.blue : theme.peach)
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: "•"
                                            font.pixelSize: 10
                                            color: theme.subtext1
                                        }

                                        Text {
                                            text: itemData.type === "playlist"
                                                  ? (itemData.description ? itemData.description : (itemData.num_tracks + " temas"))
                                                  : (itemData.type === "album"
                                                     ? (itemData.year ? itemData.year + " (" + itemData.num_tracks + " temas)" : itemData.num_tracks + " temas")
                                                     : (itemData.album || ""))
                                            font.family: "JetBrains Mono"
                                            font.pixelSize: 11
                                            color: theme.subtext1
                                            elide: Text.ElideRight
                                            width: Math.min(implicitWidth, 220)
                                        }
                                    }
                                }

                                // Información adicional a la derecha (Duración / Calidad / Pistas / Explorar)
                                Column {
                                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                                    spacing: 3

                                    Text {
                                        anchors.right: parent.right
                                        text: (itemData.type === "album" || itemData.type === "playlist")
                                              ? (itemData.num_tracks + " pistas")
                                              : (itemData.duration_str || "")
                                        font.family: "JetBrains Mono"
                                        font.pixelSize: 11
                                        font.bold: true
                                        color: isSelected ? theme.text : theme.subtext0
                                    }

                                    // Badge para Álbumes / Playlists ("Explorar ➔")
                                    Rectangle {
                                        anchors.right: parent.right
                                        height: 16
                                        width: exploreBadgeText.implicitWidth + 8
                                        radius: 4
                                        color: Qt.alpha(root.currentAccent, isSelected ? 0.35 : 0.18)
                                        border.color: Qt.alpha(root.currentAccent, 0.60)
                                        border.width: 1
                                        visible: itemData.type === "album" || itemData.type === "playlist"

                                        Text {
                                            id: exploreBadgeText
                                            anchors.centerIn: parent
                                            text: "Explorar ➔"
                                            font.family: "JetBrains Mono"
                                            font.pixelSize: 9
                                            font.bold: true
                                            color: root.currentAccent
                                        }
                                    }

                                    // Badge de calidad para pistas individuales con colores oficiales de Tidal
                                    Rectangle {
                                        id: qualityBadge
                                        readonly property string qUpper: ((itemData && itemData.quality) ? itemData.quality : "").toUpperCase()
                                        readonly property color badgeColor: {
                                            if (qUpper.indexOf("HI_RES") !== -1 || qUpper.indexOf("MAX") !== -1) return "#f5c542"; // Tidal Gold
                                            if (qUpper.indexOf("LOSSLESS") !== -1 || qUpper.indexOf("FLAC") !== -1) return "#00d2ff"; // Tidal Cyan
                                            if (qUpper.indexOf("LOW") !== -1) return "#a6adc8"; // Muted Gray
                                            return "#74c7ec"; // High / AAC
                                        }
                                        anchors.right: parent.right
                                        height: 15
                                        width: qualityText.implicitWidth + 8
                                        radius: 3
                                        color: Qt.alpha(badgeColor, 0.12)
                                        border.color: Qt.alpha(badgeColor, 0.35)
                                        border.width: 1
                                        visible: !!(itemData && itemData.type === "track" && itemData.quality)

                                        Text {
                                            id: qualityText
                                            anchors.centerIn: parent
                                            text: {
                                                if (qualityBadge.qUpper.indexOf("HI_RES") !== -1 || qualityBadge.qUpper.indexOf("MAX") !== -1) return "HI-RES";
                                                if (qualityBadge.qUpper.indexOf("LOSSLESS") !== -1 || qualityBadge.qUpper.indexOf("FLAC") !== -1) return "FLAC";
                                                if (qualityBadge.qUpper.indexOf("LOW") !== -1) return "LOW";
                                                if (qualityBadge.qUpper.indexOf("HIGH") !== -1) return "HIGH";
                                                return qualityBadge.qUpper.replace("AUDIOQUALITY.", "");
                                            }
                                            font.family: "JetBrains Mono"
                                            font.pixelSize: 9
                                            font.bold: false
                                            color: qualityBadge.badgeColor
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Estado de carga o vacío
                    Column {
                        anchors.centerIn: parent
                        spacing: 8
                        visible: resultsList.count === 0

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: backend.isSearching ? "󰄲" : "󰎆"
                            font.pixelSize: 32
                            color: theme.subtext1
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: backend.statusText
                            font.family: "JetBrains Mono"
                            font.pixelSize: 12
                            color: theme.subtext1
                        }
                    }
                }

                // ================= FOOTER =================
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "[↑/↓] Navegar"
                        font.family: "JetBrains Mono"
                        font.pixelSize: 11
                        color: theme.subtext1
                    }

                    Text {
                        text: "•"
                        font.pixelSize: 10
                        color: theme.subtext1
                    }

                    Text {
                        text: root.isTrackMode ? "[Enter] Reproducir en Mosaico" : "[Enter] Explorar canciones"
                        font.family: "JetBrains Mono"
                        font.pixelSize: 11
                        color: root.currentAccent
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: resultsList.count > 0 ? (resultsList.currentIndex + 1) + " de " + resultsList.count + " resultados" : ""
                        font.family: "JetBrains Mono"
                        font.pixelSize: 11
                        color: theme.subtext1
                    }
                }
            }

            // ========================================================
            // VISTA 2: DETALLE DE ÁLBUM / PLAYLIST
            // ========================================================
            ColumnLayout {
                id: detailView
                anchors.fill: parent
                spacing: 12
                visible: opacity > 0
                opacity: backend.isDetailView ? 1 : 0
                enabled: backend.isDetailView

                Behavior on opacity { NumberAnimation { duration: 160 } }

                // Top bar de navegación
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    // Botón Volver
                    Rectangle {
                        id: backBtn
                        Layout.preferredHeight: 34
                        Layout.preferredWidth: 105
                        radius: 8
                        color: backMouse.containsMouse ? Qt.alpha(theme.surface1, 0.9) : Qt.alpha(theme.surface0, 0.7)
                        border.color: backMouse.containsMouse ? root.currentAccent : Qt.alpha(theme.surface2, 0.6)
                        border.width: 1

                        Behavior on color { ColorAnimation { duration: 140 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }

                        Row {
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                text: "←"
                                font.family: "JetBrains Mono"
                                font.pixelSize: 13
                                font.bold: true
                                color: backMouse.containsMouse ? root.currentAccent : theme.text
                            }
                            Text {
                                text: "Volver"
                                font.family: "JetBrains Mono"
                                font.pixelSize: 12
                                font.bold: true
                                color: backMouse.containsMouse ? root.currentAccent : theme.text
                            }
                        }

                        MouseArea {
                            id: backMouse
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            hoverEnabled: true
                            onClicked: {
                                backend.closeDetail();
                            }
                        }
                    }

                    // Tipo de elemento (ÁLBUM / PLAYLIST)
                    Rectangle {
                        height: 24
                        width: typeBadgeText.implicitWidth + 16
                        radius: 6
                        color: Qt.alpha(root.currentAccent, 0.20)
                        border.color: Qt.alpha(root.currentAccent, 0.60)
                        border.width: 1

                        Text {
                            id: typeBadgeText
                            anchors.centerIn: parent
                            text: backend.detailData ? (backend.detailData.type === "playlist" ? (backend.detailData.is_user ? "📑 MI PLAYLIST" : "📑 PLAYLIST") : "💿 ÁLBUM") : ""
                            font.family: "JetBrains Mono"
                            font.pixelSize: 10
                            font.bold: true
                            color: root.currentAccent
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: "[Esc] Volver a la lista"
                        font.family: "JetBrains Mono"
                        font.pixelSize: 11
                        color: theme.subtext1
                    }
                }

                // Hero Header con Carátula, Info y Botón de Reproducir Todo
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 74
                    radius: 10
                    color: Qt.alpha(theme.surface0, 0.55)
                    border.color: Qt.alpha(theme.surface1, 0.70)
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 14

                        // Carátula destacada
                        Rectangle {
                            Layout.preferredWidth: 54
                            Layout.preferredHeight: 54
                            radius: 8
                            color: Qt.alpha(theme.surface1, 0.8)
                            border.color: Qt.alpha(root.currentAccent, 0.5)
                            border.width: 1.5
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: (backend.detailData && backend.detailData.cover_url) ? backend.detailData.cover_url : ""
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                visible: status === Image.Ready
                            }

                            Text {
                                anchors.centerIn: parent
                                text: (backend.detailData && backend.detailData.type === "playlist") ? "📑" : "💿"
                                font.pixelSize: 22
                                visible: !backend.detailData || !backend.detailData.cover_url || parent.children[0].status !== Image.Ready
                            }
                        }

                        // Metadatos
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3

                            Text {
                                text: backend.detailData ? (backend.detailData.name || "") : ""
                                font.family: "JetBrains Mono"
                                font.pixelSize: 14
                                font.bold: true
                                color: theme.text
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            Row {
                                spacing: 8
                                Text {
                                    text: backend.detailData ? ((backend.detailData.artist || backend.detailData.creator) || "") : ""
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: root.currentAccent
                                }

                                Text {
                                    text: "•"
                                    font.pixelSize: 10
                                    color: theme.subtext1
                                }

                                Text {
                                    text: backend.detailData ? (backend.detailData.num_tracks + " temas") : ""
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 11
                                    color: theme.subtext1
                                }
                            }
                        }

                        // Botón Reproducir Todo
                        Rectangle {
                            id: playAllBtn
                            Layout.preferredHeight: 36
                            Layout.preferredWidth: 160
                            radius: 8
                            color: playAllMouse.containsMouse ? Qt.lighter(root.currentAccent, 1.15) : root.currentAccent

                            Behavior on color { ColorAnimation { duration: 120 } }

                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Text {
                                    text: "▶"
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: theme.crust
                                }
                                Text {
                                    text: "Reproducir todo"
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: theme.crust
                                }
                            }

                            MouseArea {
                                id: playAllMouse
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                onClicked: {
                                    backend.playAllFromDetail();
                                    root.close();
                                }
                            }
                        }
                    }
                }

                // Barra de filtrado rápido de temas en la colección
                Rectangle {
                    id: detailSearchContainer
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: 8
                    color: Qt.alpha(theme.surface0, 0.60)
                    border.color: detailSearchInput.activeFocus ? root.currentAccent : Qt.alpha(theme.surface1, 0.65)
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 8

                        Text {
                            text: "🔍"
                            font.pixelSize: 12
                            color: detailSearchInput.activeFocus ? root.currentAccent : theme.subtext1
                        }

                        TextInput {
                            id: detailSearchInput
                            Layout.fillWidth: true
                            font.family: "JetBrains Mono"
                            font.pixelSize: 12
                            color: theme.text
                            clip: true
                            selectByMouse: true

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Filtrar canciones de esta lista (ej: título, artista)..."
                                font.family: "JetBrains Mono"
                                font.pixelSize: 11
                                color: theme.subtext1
                                opacity: detailSearchInput.text.length === 0 ? 0.6 : 0.0
                            }

                            onTextChanged: {
                                backend.filterDetailTracks(text);
                            }

                            Keys.onDownPressed: function(event) {
                                if (detailTrackList.count > 0) {
                                    if (detailTrackList.currentIndex < detailTrackList.count - 1) {
                                        detailTrackList.currentIndex++;
                                    } else {
                                        detailTrackList.currentIndex = 0;
                                    }
                                    detailTrackList.positionViewAtIndex(detailTrackList.currentIndex, ListView.Contain);
                                    backend.playSwitchSound();
                                }
                                event.accepted = true;
                            }

                            Keys.onUpPressed: function(event) {
                                if (detailTrackList.count > 0) {
                                    if (detailTrackList.currentIndex > 0) {
                                        detailTrackList.currentIndex--;
                                    } else {
                                        detailTrackList.currentIndex = detailTrackList.count - 1;
                                    }
                                    detailTrackList.positionViewAtIndex(detailTrackList.currentIndex, ListView.Contain);
                                    backend.playSwitchSound();
                                }
                                event.accepted = true;
                            }

                            Keys.onReturnPressed: function(event) {
                                if (detailTrackList.count > 0 && detailTrackList.currentIndex >= 0) {
                                    backend.playFromDetail(detailTrackList.currentIndex);
                                    root.close();
                                }
                                event.accepted = true;
                            }

                            Keys.onEscapePressed: function(event) {
                                if (text.length > 0) {
                                    text = "";
                                } else {
                                    backend.closeDetail();
                                    searchInput.forceFocus();
                                }
                                event.accepted = true;
                            }
                        }

                        Text {
                            text: "✕"
                            font.pixelSize: 11
                            color: theme.subtext1
                            visible: detailSearchInput.text.length > 0
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    detailSearchInput.text = "";
                                }
                            }
                        }
                    }
                }

                // Lista de Canciones del Álbum o Playlist
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 10
                    color: Qt.alpha(theme.surface0, 0.40)
                    border.color: Qt.alpha(theme.surface1, 0.50)
                    border.width: 1
                    clip: true

                    // Indicador de carga
                    Column {
                        anchors.centerIn: parent
                        spacing: 10
                        visible: backend.isLoadingDetail

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "⏳"
                            font.pixelSize: 28
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "Cargando canciones..."
                            font.family: "JetBrains Mono"
                            font.pixelSize: 12
                            color: theme.subtext0
                        }
                    }

                    // Estado vacío
                    Column {
                        anchors.centerIn: parent
                        spacing: 8
                        visible: !backend.isLoadingDetail && backend.detailTracks.length === 0

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "󰎆"
                            font.pixelSize: 28
                            color: theme.subtext1
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: "No se encontraron temas en esta colección."
                            font.family: "JetBrains Mono"
                            font.pixelSize: 12
                            color: theme.subtext1
                        }
                    }

                    ListView {
                        id: detailTrackList
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 2
                        clip: true
                        visible: !backend.isLoadingDetail
                        model: backend.detailTracks

                        highlight: Rectangle {
                            radius: 6
                            color: Qt.alpha(root.currentAccent, 0.22)
                            border.color: Qt.alpha(root.currentAccent, 0.65)
                            border.width: 1.2
                            z: 2
                            Behavior on y { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
                        }
                        highlightFollowsCurrentItem: true
                        highlightMoveDuration: 120

                        focus: false

                        Keys.onPressed: function(event) {
                            handleGlobalKey(event);
                        }

                        delegate: Item {
                            width: detailTrackList.width
                            height: 42

                            readonly property bool isSelected: ListView.isCurrentItem
                            readonly property var trackItem: modelData

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                onEntered: {
                                    detailTrackList.currentIndex = index;
                                }
                                onClicked: {
                                    detailTrackList.currentIndex = index;
                                    backend.playFromDetail(index);
                                    root.close();
                                }
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 12
                                spacing: 10

                                // Número de pista
                                Text {
                                    Layout.preferredWidth: 26
                                    horizontalAlignment: Text.AlignRight
                                    text: trackItem.track_num ? (trackItem.track_num + "") : ((index + 1) + "")
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: isSelected ? root.currentAccent : theme.subtext1
                                }

                                // Título de la pista
                                Text {
                                    text: trackItem.name || ""
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 12
                                    font.bold: true
                                    color: isSelected ? theme.text : theme.subtext0
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }

                                // Badge explícito
                                Rectangle {
                                    visible: !!trackItem.explicit
                                    width: 14
                                    height: 14
                                    radius: 3
                                    color: Qt.alpha(theme.red, 0.3)
                                    border.color: theme.red
                                    border.width: 1
                                    Text {
                                        anchors.centerIn: parent
                                        text: "E"
                                        font.pixelSize: 9
                                        font.bold: true
                                        color: theme.red
                                    }
                                }

                                // Artista de la pista
                                Text {
                                    text: trackItem.artist || ""
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 11
                                    color: isSelected ? root.currentAccent : theme.subtext1
                                    elide: Text.ElideRight
                                    Layout.preferredWidth: 160
                                    visible: !!trackItem.artist
                                }

                                // Badge de calidad con colores oficiales de Tidal
                                Rectangle {
                                    id: detailQualityBadge
                                    readonly property string qUpper: ((trackItem && trackItem.quality) ? trackItem.quality : "").toUpperCase()
                                    readonly property color badgeColor: {
                                        if (qUpper.indexOf("HI_RES") !== -1 || qUpper.indexOf("MAX") !== -1) return "#f5c542"; // Tidal Gold
                                        if (qUpper.indexOf("LOSSLESS") !== -1 || qUpper.indexOf("FLAC") !== -1) return "#00d2ff"; // Tidal Cyan
                                        if (qUpper.indexOf("LOW") !== -1) return "#a6adc8"; // Muted Gray
                                        return "#74c7ec"; // High / AAC
                                    }
                                    height: 15
                                    width: detailQualityText.implicitWidth + 6
                                    radius: 3
                                    color: Qt.alpha(badgeColor, 0.12)
                                    border.color: Qt.alpha(badgeColor, 0.35)
                                    border.width: 1
                                    visible: !!(trackItem && trackItem.quality)

                                    Text {
                                        id: detailQualityText
                                        anchors.centerIn: parent
                                        text: {
                                            if (detailQualityBadge.qUpper.indexOf("HI_RES") !== -1 || detailQualityBadge.qUpper.indexOf("MAX") !== -1) return "HI-RES";
                                            if (detailQualityBadge.qUpper.indexOf("LOSSLESS") !== -1 || detailQualityBadge.qUpper.indexOf("FLAC") !== -1) return "FLAC";
                                            if (detailQualityBadge.qUpper.indexOf("LOW") !== -1) return "LOW";
                                            if (detailQualityBadge.qUpper.indexOf("HIGH") !== -1) return "HIGH";
                                            return detailQualityBadge.qUpper.replace("AUDIOQUALITY.", "");
                                        }
                                        font.family: "JetBrains Mono"
                                        font.pixelSize: 8
                                        font.bold: false
                                        color: detailQualityBadge.badgeColor
                                    }
                                }

                                // Duración
                                Text {
                                    text: trackItem.duration_str || ""
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 11
                                    font.bold: true
                                    color: isSelected ? theme.text : theme.subtext0
                                }
                            }
                        }
                    }
                }

                // Footer de Detalle
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "[↑/↓] Navegar"
                        font.family: "JetBrains Mono"
                        font.pixelSize: 11
                        color: theme.subtext1
                    }

                    Text {
                        text: "•"
                        font.pixelSize: 10
                        color: theme.subtext1
                    }

                    Text {
                        text: "[Enter] Reproducir desde aquí"
                        font.family: "JetBrains Mono"
                        font.pixelSize: 11
                        color: root.currentAccent
                    }

                    Text {
                        text: "•"
                        font.pixelSize: 10
                        color: theme.subtext1
                    }

                    Text {
                        text: "[P] Reproducir todo"
                        font.family: "JetBrains Mono"
                        font.pixelSize: 11
                        color: theme.peach
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: detailTrackList.count > 0 ? (detailTrackList.currentIndex + 1) + " de " + detailTrackList.count + " temas" : ""
                        font.family: "JetBrains Mono"
                        font.pixelSize: 11
                        color: theme.subtext1
                    }
                }
            }
        }
    }
}
