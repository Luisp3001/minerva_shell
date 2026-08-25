// optional/Minerva/ChatWidget.qml — Interfaz de chat completa del plugin Minerva
// Recibe mensajes del backend vía señal aiWidget.backendMessage y renderiza
// burbujas de chat, tarjetas de comandos y diálogo de confirmación.
import QtQuick
import Quickshell
import Quickshell.Io
import Qt.labs.folderlistmodel
import "../../style"

Item {
    id: root

    // Referencia al Main.qml del plugin (inyectada desde expandedPanel)
    property var aiWidget: null

    // ── Estado de la conversación y del diálogo ───────────────────────────
    // Ahora todo el estado reside en aiWidget (Main.qml) para persistencia.
    // Solo referenciamos sus propiedades.

    // ── Escuchar mensajes del backend ─────────────────────────────────────
    Connections {
        target: root.aiWidget
        function onBackendMessage(msg) { root.handleMsg(msg) }
    }

    // ── Autocomplete properties ───────────────────────────────────────────
    property bool showSuggestions: false
    property string currentSearchDir: ""
    property string currentSearchFilter: ""
    property int currentCursorStart: -1
    property int currentCursorEnd: -1
    property var pathAliases: ({})

    FolderListModel {
        id: fileSuggestionModel
        folder: root.currentSearchDir ? "file://" + root.currentSearchDir : ""
        showDirsFirst: true
        onStatusChanged: {
            if (status === FolderListModel.Ready) root.updateFuzzyList()
        }
        onCountChanged: root.updateFuzzyList()
    }

    ListModel {
        id: fuzzySuggestionsModel
    }

    function fuzzyMatch(str, pattern) {
        if (!pattern) return true
        pattern = pattern.toLowerCase()
        str = str.toLowerCase()
        var patternIdx = 0
        var strIdx = 0
        while (patternIdx < pattern.length && strIdx < str.length) {
            if (pattern[patternIdx] === str[strIdx]) {
                patternIdx++
            }
            strIdx++
        }
        return patternIdx === pattern.length
    }

    function updateFuzzyList() {
        fuzzySuggestionsModel.clear()
        if (!root.showSuggestions) return
        var filter = root.currentSearchFilter
        var maxResults = 15
        for (var i = 0; i < fileSuggestionModel.count; i++) {
            if (fuzzySuggestionsModel.count >= maxResults) break
            var fileName = fileSuggestionModel.get(i, "fileName")
            var isDir = fileSuggestionModel.get(i, "fileIsDir")
            if (fileName === "." || fileName === "..") continue
            
            if (filter === "" || fuzzyMatch(fileName, filter)) {
                fuzzySuggestionsModel.append({
                    "fileName": fileName,
                    "isDir": isDir
                })
            }
        }
        if (fuzzySuggestionsModel.count > 0 && suggestionsList.currentIndex < 0) {
            suggestionsList.currentIndex = 0
        }
    }

    function checkAutocomplete() {
        var text = inputField.text
        var cpos = inputField.cursorPosition
        
        var start = -1
        var mode = 0 
        for (var i = cpos - 1; i >= 0; i--) {
            if (text[i] === ']' || text[i] === ' ' || text[i] === '\n') {
                break
            }
            if (text[i] === '@') {
                if (i < text.length - 1 && text[i+1] === '[') {
                    start = i
                    mode = 2
                    break
                }
                start = i
                mode = 1
                break
            }
        }

        if (start !== -1) {
            var prefixLen = (mode === 2) ? 2 : 1
            var searchStr = text.substring(start + prefixLen, cpos)
            
            var dir = Quickshell.env("HOME")
            var filter = searchStr
            
            if (searchStr.indexOf('/') !== -1) {
                var lastSlash = searchStr.lastIndexOf('/')
                var subDir = searchStr.substring(0, lastSlash)
                if (subDir.startsWith("/")) {
                    dir = subDir
                } else if (subDir.startsWith("~")) {
                    dir = Quickshell.env("HOME") + subDir.substring(1)
                } else {
                    dir = Quickshell.env("HOME") + "/" + subDir
                }
                filter = searchStr.substring(lastSlash + 1)
            } else if (searchStr.startsWith("~")) {
                dir = Quickshell.env("HOME")
                filter = searchStr.substring(1)
            } else if (searchStr.startsWith("/")) {
                dir = "/"
                filter = searchStr.substring(1)
            }
            
            root.currentSearchDir = dir
            root.currentSearchFilter = filter
            root.currentCursorStart = start
            root.currentCursorEnd = cpos
            root.showSuggestions = true
            root.updateFuzzyList()
        } else {
            root.showSuggestions = false
        }
    }

    function toChipText(str, isDir) {
        var result = "";
        for (var i = 0; i < str.length; i++) {
            var code = str.charCodeAt(i);
            if (code >= 65 && code <= 90) {
                result += String.fromCodePoint(code + 120211);
            } else if (code >= 97 && code <= 122) {
                result += String.fromCodePoint(code + 120205);
            } else if (code >= 48 && code <= 57) {
                result += String.fromCodePoint(code + 120764);
            } else {
                result += str[i];
            }
        }
        var icon = isDir ? "󰉋 " : "󰈔 ";
        return icon + result;
    }

    function acceptSuggestion(fileName, isDir) {
        var text = inputField.text
        var originalSearch = text.substring(root.currentCursorStart, root.currentCursorEnd)
        var lastSlash = originalSearch.lastIndexOf('/')
        var pathPrefix = ""
        if (lastSlash !== -1) {
            pathPrefix = originalSearch.substring(0, lastSlash + 1)
            if (!pathPrefix.startsWith("@[")) {
                pathPrefix = "@[" + pathPrefix.substring(1)
            }
        } else {
            pathPrefix = "@["
        }
        
        var newStr = ""
        if (isDir) {
            newStr = pathPrefix + fileName + "/"
        } else {
            var cleanDir = root.currentSearchDir
            if (cleanDir.endsWith("/")) cleanDir = cleanDir.substring(0, cleanDir.length - 1)
            var fullPath = cleanDir + "/" + fileName
            
            var baseAlias = root.toChipText(fileName, false)
            var aliasKey = baseAlias
            var counter = 1
            while (root.pathAliases[aliasKey] && root.pathAliases[aliasKey] !== "@[" + fullPath + "]") {
                aliasKey = root.toChipText(fileName + " (" + counter + ")", false)
                counter++
            }
            
            root.pathAliases[aliasKey] = "@[" + fullPath + "]"
            newStr = aliasKey + " "
        }
        
        var before = text.substring(0, root.currentCursorStart)
        var after = text.substring(root.currentCursorEnd)
        inputField.text = before + newStr + after
        inputField.cursorPosition = (before + newStr).length
        if (!isDir) {
            root.showSuggestions = false
        }
    }

    // ── Manejadores de mensajes ───────────────────────────────────────────
    function handleMsg(msg) {
        switch (msg.type) {
            case "token":
                onToken(msg.content || "")
                break
            case "done":
                onDone(msg.full_response || "")
                break
            case "tool_start":
                addSystemMsg(toolLabel(msg.tool || "", msg.args || {}))
                break
            case "tool_result":
                break   // interno, no mostrar
            case "run_command":
                // Comando seguro: se auto-ejecuta, se muestra como "running"
                aiWidget.msgModel.append({
                    role: "command", content: msg.command || "", command: msg.command || "",
                    jobId: msg.job_id || "",
                    cmdStatus: "running", needsConfirm: false, needsSudo: false, isSystem: false
                })
                scrollToBottom()
                break
            case "confirm_required":
                addCmdCard(msg.command || "", msg.job_id || "", true, false)
                aiWidget.pendingCmd    = msg.command || ""
                aiWidget.pendingJobId  = msg.job_id  || ""
                aiWidget.pendingIsSudo = false
                aiWidget.pendingReason = msg.reason  || "Comando potencialmente destructivo"
                if (!(aiWidget.shellRoot && aiWidget.shellRoot.commandApprovalOpen)) {
                    aiWidget.showConfirm = true
                }
                break
            case "sudo_required":
                addCmdCard(msg.command || "", msg.job_id || "", false, true)
                aiWidget.pendingCmd    = msg.command || ""
                aiWidget.pendingJobId  = msg.job_id  || ""
                aiWidget.pendingIsSudo = true
                aiWidget.pendingReason = "Este comando requiere permisos de administrador (pkexec)"
                if (!(aiWidget.shellRoot && aiWidget.shellRoot.commandApprovalOpen)) {
                    aiWidget.showConfirm = true
                }
                break
            case "command_start": {
                // Marcar la command card como "done" buscando por job_id
                var startJobId = msg.job_id || ""
                for (var ci = aiWidget.msgModel.count - 1; ci >= 0; ci--) {
                    var citem = aiWidget.msgModel.get(ci)
                    if (citem.role === "command" && citem.jobId === startJobId) {
                        aiWidget.msgModel.setProperty(ci, "cmdStatus", "done")
                        break
                    }
                }
                addResultCard(msg.command || "", startJobId, "", "running")
                break
            }
            case "command_output": {
                // Actualizar la result card correcta por job_id
                var outJobId = msg.job_id || ""
                for (var ri = aiWidget.msgModel.count - 1; ri >= 0; ri--) {
                    var ritem = aiWidget.msgModel.get(ri)
                    if (ritem.role === "result" && ritem.jobId === outJobId) {
                        aiWidget.msgModel.setProperty(ri, "content", ritem.content + (msg.text || ""))
                        break
                    }
                }
                scrollToBottom()
                break
            }
            case "command_result": {
                // Finalizar la result card correcta por job_id
                var resJobId = msg.job_id || ""
                var found = false
                for (var resi = aiWidget.msgModel.count - 1; resi >= 0; resi--) {
                    var resitem = aiWidget.msgModel.get(resi)
                    if (resitem.role === "result" && resitem.jobId === resJobId) {
                        aiWidget.msgModel.setProperty(resi, "cmdStatus", (msg.success !== false) ? "success" : "error")
                        // Volcar el output solo si la card estaba vacía (sin command_output previo)
                        if (!resitem.content && msg.output) {
                            aiWidget.msgModel.setProperty(resi, "content", msg.output)
                        }
                        found = true
                        break
                    }
                }
                if (!found) {
                    // Fallback: crear result card directamente (no llegó command_start)
                    addResultCard(msg.command || "", resJobId, msg.output || "", (msg.success !== false) ? "success" : "error")
                }
                break
            }
            case "error":
                if (aiWidget.streamingIdx >= 0) {
                    aiWidget.streamingIdx = -1
                    aiWidget.streamingRaw = ""
                }
                addSystemMsg("⚠ " + (msg.message || "Error desconocido"))
                break
        }
    }

    function toolLabel(t, args) {
        if (t === "list_dir") {
            let p = args && args.path ? args.path.split('/').pop() : ""
            return "󰏗  Listando directorio" + (p ? " " + p + "…" : "…")
        }
        if (t === "read_file" || t === "read_pdf" || t === "read_docx" || t === "read_pptx" || t === "read_excel") {
            let msg = "󰈙  Leyendo archivo"
            if (args && args.path) {
                let p = args.path.split('/').pop()
                msg += " " + p
            }
            if (args && args.start_line !== undefined && args.end_line !== undefined) {
                msg += " (líneas " + args.start_line + "-" + args.end_line + ")"
            }
            return msg + "…"
        }
        if (t === "run_command") return "󰆍  Preparando comando…"
        if (t === "web_search") {
            let q = args && args.query ? args.query : ""
            return "󰖟  Buscando en internet" + (q ? ": " + q + "…" : "…")
        }
        if (t === "update_memory") return "󰋊  Guardando en memoria…"
        if (t === "spotify_music") return "󰓇  Controlando Spotify…"
        if (t === "manage_tasks") return "󰃭  Gestionando tareas…"
        if (t === "capture_screen") return "󰹑  Tomando captura de pantalla…"
        if (t === "write_file") return "󰏚  Escribiendo archivo…"
        if (t === "replace_lines") return "󰏚  Editando archivo…"
        if (t === "create_docx" || t === "modify_docx") return "󰏚  Modificando documento…"
        if (t === "query_document") return "󰈙  Consultando documento…"
        if (t === "launch_app") return "󰀨  Lanzando aplicación…"
        if (t === "file_info") return "󰋽  Consultando metadatos…"
        return "󰏗  Usando herramienta…"
    }

    // ── Helpers de modelo ─────────────────────────────────────────────────
    function onToken(tok) {
        scrollToBottom()
    }

    function onDone(fullRaw) {
        scrollToBottom()
    }

    function addSystemMsg(text) {
        aiWidget.msgModel.append({
            role: "system", content: text, command: "", cmdStatus: "", jobId: "",
            needsConfirm: false, needsSudo: false, isSystem: true
        })
        scrollToBottom()
    }

    function addCmdCard(cmd, jobId, needsConfirm, needsSudo) {
        aiWidget.msgModel.append({
            role: "command", content: cmd, command: cmd, jobId: jobId,
            cmdStatus: "pending",
            needsConfirm: needsConfirm, needsSudo: needsSudo, isSystem: false
        })
        scrollToBottom()
    }

    function addResultCard(cmd, jobId, output, status) {
        aiWidget.msgModel.append({
            role: "result", content: output, command: cmd, jobId: jobId,
            cmdStatus: status,
            needsConfirm: false, needsSudo: false, isSystem: false
        })
        scrollToBottom()
    }

    function sendMessage() {
        var text = inputField.text.trim()
        if (!text || !root.aiWidget || root.aiWidget.isThinking) return

        inputField.text = ""
        aiWidget.currentUserMsg = text
        
        var textToSend = text
        for (var key in root.pathAliases) {
            textToSend = textToSend.split(key).join(root.pathAliases[key])
        }

        // Añadir burbuja de usuario
        aiWidget.msgModel.append({
            role: "user", content: text, command: "", cmdStatus: "",
            needsConfirm: false, needsSudo: false, isSystem: false
        })
        scrollToBottom()

        // Enviar al backend (historial sin el mensaje actual; backend lo añade)
        root.aiWidget.sendChat(textToSend, aiWidget.conversationHistory.slice())
    }

    function clearChat() {
        aiWidget.msgModel.clear()
        aiWidget.conversationHistory = []
        root.pathAliases = ({})
        aiWidget.currentUserMsg  = ""
        aiWidget.streamingIdx    = -1
        aiWidget.streamingRaw    = ""
        aiWidget.pendingCmd      = ""
        aiWidget.pendingJobId    = ""
        aiWidget.showConfirm     = false
        if (root.aiWidget) root.aiWidget.cancelRun()
    }

    function scrollToBottom() {
        Qt.callLater(function() { chatFlickable.positionViewAtEnd() })
    }

    // ── UI ────────────────────────────────────────────────────────────────
    Column {
        anchors.fill: parent
        spacing: 0

        // ── Header ────────────────────────────────────────────────────────
        Rectangle {
            id: chatHeader
            width:  parent.width
            height: 46
            color:  Qt.rgba(1, 1, 1, 0.04)

            // Izquierda: icono + nombre + dot de estado
            Row {
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10

                Text {
                    text: root.aiWidget && root.aiWidget.isRecording ? "󰍬" : "󱜚"
                    font.family: Theme.fontMono
                    font.pixelSize: 20
                    color: root.aiWidget && root.aiWidget.isRecording ? Theme.danger : Theme.accent
                    anchors.verticalCenter: parent.verticalCenter
                }

                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    Text {
                        text: "Minerva"
                        font.family: Theme.fontSans
                        font.pixelSize: 13
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                    }
                    Text {
                        text: root.aiWidget ? root.aiWidget.modelName : "…"
                        font.family: Theme.fontMono
                        font.pixelSize: 9
                        color: Theme.textMuted
                    }
                }

                Rectangle {
                    width: 7; height: 7; radius: 3.5
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.aiWidget && root.aiWidget.isRecording ? Theme.danger
                         : root.aiWidget && root.aiWidget.isThinking  ? Theme.warning
                         : root.aiWidget && root.aiWidget.backendReady ? Theme.success
                         : Theme.danger
                    Behavior on color { ColorAnimation { duration: 300 } }
                    SequentialAnimation on opacity {
                        running: root.aiWidget && (root.aiWidget.isThinking || root.aiWidget.isRecording)
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.15; duration: 500 }
                        NumberAnimation { to: 1.0;  duration: 500 }
                        onStopped: opacity = 1.0
                    }
                }
                
                Text {
                    text: "󰍬"
                    font.family: Theme.fontMono
                    font.pixelSize: 14
                    color: Theme.accent
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.aiWidget && root.aiWidget.backendReady && !root.aiWidget.isRecording && !root.aiWidget.isTranscribing && !root.aiWidget.isThinking
                    opacity: 0.5
                }
            }

            // Derecha: botón reiniciar conversación
            Item {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                width: 30; height: 30

                Rectangle {
                    anchors.fill: parent; radius: 8
                    color: clearHover.containsMouse ? Qt.rgba(1,1,1,0.08) : "transparent"
                    Behavior on color { ColorAnimation { duration: 150 } }
                }
                Text {
                    anchors.centerIn: parent
                    text: "󰑐"
                    font.family: Theme.fontMono
                    font.pixelSize: 15
                    color: clearHover.containsMouse ? Theme.warning : Theme.textMuted
                    Behavior on color { ColorAnimation { duration: 150 } }
                }
                MouseArea {
                    id: clearHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.clearChat()
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width; height: 1
                color: Qt.rgba(1, 1, 1, 0.07)
            }
        }

        // ── Área de mensajes ──────────────────────────────────────────────
        Item {
            width:  parent.width
            height: parent.height - chatHeader.height - inputBar.height

            // ListView virtualiza: solo instancia los delegates visibles +
            // cacheBuffer. Antes (Repeater+Column) se creaban todos de golpe.
            ListView {
                id: chatFlickable
                anchors.fill: parent
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.VerticalFlick
                // ~3 pantallas de buffer: scroll suave sin cargar todo
                cacheBuffer: height * 3
                spacing: 8
                topMargin:    10
                bottomMargin: 10
                leftMargin:   10
                rightMargin:  10

                // Al abrir el panel, ir directo al último mensaje
                Component.onCompleted: Qt.callLater(positionViewAtEnd)
                // Auto-scroll cuando llega un mensaje nuevo
                onCountChanged: Qt.callLater(positionViewAtEnd)

                model: root.aiWidget ? root.aiWidget.msgModel : null

                delegate: Item {
                    id: msgDelegate
                    // ListView necesita width explícito en el delegate
                    width: chatFlickable.width - 20
                    height: msgLoader.implicitHeight

                    // Loader: solo instancia el componente correcto según rol.
                    // Evita crear los 3 tipos de burbuja por cada mensaje.
                    Loader {
                        id: msgLoader
                        width: parent.width
                        sourceComponent: {
                            if (model.role === "user")    return userBubbleComp
                            if (model.role === "ai")      return aiBubbleComp
                            if (model.role === "command" || model.role === "result") return cmdCardComp
                            if (model.isSystem)           return sysMsgComp
                            return null
                        }
                    }

                    // ── Burbuja usuario ───────────────────────────────────
                    Component {
                        id: userBubbleComp
                        Item {
                            implicitHeight: _userBubble.implicitHeight
                            Rectangle {
                                id: _userBubble
                                implicitHeight: _userTxt.implicitHeight + 18
                                width: Math.min(_userTxt.implicitWidth + 30, msgDelegate.width * 0.82)
                                anchors.right: parent.right
                                radius: 16
                                color: Theme.accent
                                TextEdit {
                                    id: _userTxt
                                    anchors.centerIn: parent
                                    width: parent.width - 30
                                    text: model.content
                                    font.family: Theme.fontSans
                                    font.pixelSize: 13
                                    color: "#0d0d0d"
                                    wrapMode: TextEdit.Wrap
                                    readOnly: true
                                    selectByMouse: true
                                }
                            }
                        }
                    }

                    // ── Burbuja IA ────────────────────────────────────────
                    Component {
                        id: aiBubbleComp
                        Item {
                            implicitHeight: _aiBubble.implicitHeight
                            Rectangle {
                                id: _aiBubble
                                // Ancho fijo: evita el re-layout costoso de
                                // implicitWidth cuando wrapMode está activo.
                                implicitHeight: _aiTxt.implicitHeight + 18
                                width: msgDelegate.width * 0.92
                                anchors.left: parent.left
                                radius: 16
                                color: Qt.rgba(1, 1, 1, 0.07)
                                border.width: 1
                                border.color: Qt.rgba(1, 1, 1, 0.09)
                                TextEdit {
                                    id: _aiTxt
                                    anchors.centerIn: parent
                                    width: parent.width - 30
                                    text: model.content
                                        + (root.aiWidget && root.aiWidget.streamingIdx === index && root.aiWidget.isThinking ? "▋" : "")
                                    font.family: Theme.fontSans
                                    font.pixelSize: 13
                                    color: Theme.textPrimary
                                    wrapMode: TextEdit.Wrap
                                    textFormat: TextEdit.PlainText
                                    readOnly: true
                                    selectByMouse: true
                                }
                            }
                        }
                    }

                    // ── Tarjeta de comando / resultado ────────────────────
                    Component {
                        id: cmdCardComp
                        Rectangle {
                            implicitHeight: _cardCol.implicitHeight + 20
                            width: msgDelegate.width
                            radius: 14

                            color: model.role === "result"
                                ? (model.cmdStatus === "success"
                                   ? Qt.rgba(0.08, 0.28, 0.08, 0.55)
                                   : model.cmdStatus === "error"
                                     ? Qt.rgba(0.32, 0.07, 0.07, 0.55)
                                     : Qt.rgba(0.08, 0.15, 0.32, 0.55))
                                : Qt.rgba(1, 1, 1, 0.04)
                            border.width: 1
                            border.color: model.role === "result"
                                ? (model.cmdStatus === "success"
                                   ? Qt.rgba(0.3, 0.7, 0.3, 0.3)
                                   : model.cmdStatus === "error"
                                     ? Qt.rgba(0.8, 0.3, 0.3, 0.3)
                                     : Qt.rgba(0.3, 0.5, 0.8, 0.3))
                                : (model.needsConfirm || model.needsSudo)
                                  ? Qt.rgba(0.95, 0.65, 0.22, 0.45)
                                  : Qt.rgba(1, 1, 1, 0.09)

                            Column {
                                id: _cardCol
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                                spacing: 8

                                Row {
                                    spacing: 6
                                    Text {
                                        id: _resultIcon
                                        text: model.role === "result"
                                            ? (model.cmdStatus === "success" ? "󰄬" : model.cmdStatus === "error" ? "󰅖" : "󰔟")
                                            : model.needsSudo ? "󰌞"
                                            : model.needsConfirm ? "󰀦"
                                            : "󰆍"
                                        font.family: Theme.fontMono
                                        font.pixelSize: 13
                                        color: model.role === "result"
                                            ? (model.cmdStatus === "success" ? Theme.success : model.cmdStatus === "error" ? Theme.danger : Theme.accent)
                                            : (model.needsSudo || model.needsConfirm) ? Theme.warning : Theme.accent
                                        anchors.verticalCenter: parent.verticalCenter
                                        SequentialAnimation on rotation {
                                            running: model.role === "result" && model.cmdStatus === "running"
                                            loops: Animation.Infinite
                                            NumberAnimation { to: 360; duration: 900; easing.type: Easing.Linear }
                                            onStopped: _resultIcon.rotation = 0
                                        }
                                    }
                                    Text {
                                        text: model.role === "result" ? (model.cmdStatus === "running" ? "Ejecutando..." : "Resultado")
                                            : model.needsSudo ? "Requiere sudo (pkexec)"
                                            : model.needsConfirm ? "Confirmar antes de ejecutar"
                                            : "Ejecutar comando"
                                        font.family: Theme.fontSans; font.pixelSize: 11; font.weight: Font.Bold
                                        color: Theme.textMuted; anchors.verticalCenter: parent.verticalCenter
                                    }
                                }

                                Rectangle {
                                    width: _cardCol.width; height: _cmdLineTxt.implicitHeight + 12
                                    radius: 8; color: Qt.rgba(0, 0, 0, 0.35)
                                    TextEdit {
                                        id: _cmdLineTxt
                                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 10 }
                                        text: "$ " + (model.role === "result" ? model.command : model.content)
                                        font.family: Theme.fontMono; font.pixelSize: 12
                                        color: (model.needsSudo || model.needsConfirm) ? Theme.warning : Theme.accent
                                        wrapMode: TextEdit.Wrap; readOnly: true; selectByMouse: true
                                    }
                                }

                                Flickable {
                                    visible: model.role === "result" && model.content.length > 0
                                    width: _cardCol.width
                                    height: Math.min(_resultTxtEdit.implicitHeight, 230)
                                    contentWidth: width; contentHeight: _resultTxtEdit.implicitHeight
                                    clip: true; boundsBehavior: Flickable.StopAtBounds
                                    TextEdit {
                                        id: _resultTxtEdit
                                        width: parent.width; text: model.content
                                        font.family: Theme.fontMono; font.pixelSize: 11
                                        color: model.cmdStatus === "success" ? Theme.textPrimary : Theme.danger
                                        wrapMode: TextEdit.Wrap; readOnly: true; selectByMouse: true
                                    }
                                }

                                Row {
                                    visible: model.role === "command" && model.cmdStatus === "pending"
                                    spacing: 8
                                    Rectangle {
                                        height: 30; width: _execLbl.implicitWidth + 24; radius: 8
                                        color: _execMa.containsMouse ? Qt.rgba(0.15,0.5,0.15,0.9) : Qt.rgba(0.08,0.30,0.08,0.8)
                                        border.width: 1; border.color: Qt.rgba(Theme.success.r, Theme.success.g, Theme.success.b, 0.75)
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                        Row {
                                            anchors.centerIn: parent; spacing: 4
                                            Text { text: "󰄬"; font.family: Theme.fontMono; font.pixelSize: 11; color: Theme.success; anchors.verticalCenter: parent.verticalCenter }
                                            Text { id: _execLbl; text: model.needsSudo ? "Ejecutar (sudo)" : "Ejecutar"; font.family: Theme.fontSans; font.pixelSize: 12; color: Theme.success; anchors.verticalCenter: parent.verticalCenter }
                                        }
                                        MouseArea {
                                            id: _execMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                var cmd = model.content; var jobId = model.jobId || ""
                                                var isSudo = model.needsSudo; var isDestroy = model.needsConfirm
                                                if (isSudo) { root.aiWidget.msgModel.setProperty(index,"cmdStatus","running"); root.aiWidget.sudoRun(cmd, jobId) }
                                                else if (isDestroy) { root.aiWidget.pendingCmd = cmd; root.aiWidget.pendingJobId = jobId; root.aiWidget.pendingIsSudo = false; root.aiWidget.pendingReason = "Este comando puede eliminar datos de forma irreversible"; root.aiWidget.showConfirm = true }
                                                else { root.aiWidget.msgModel.setProperty(index,"cmdStatus","running"); root.aiWidget.confirmRun(cmd, jobId) }
                                            }
                                        }
                                    }
                                    Rectangle {
                                        height: 30; width: _cancelLbl.implicitWidth + 24; radius: 8
                                        color: _cancelMa.containsMouse ? Qt.rgba(0.4,0.1,0.1,0.6) : Qt.rgba(0.22,0.05,0.05,0.5)
                                        border.width: 1; border.color: Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.5)
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                        Text { id: _cancelLbl; anchors.centerIn: parent; text: "Cancelar"; font.family: Theme.fontSans; font.pixelSize: 12; color: Theme.danger }
                                        MouseArea {
                                            id: _cancelMa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                root.aiWidget.msgModel.setProperty(index, "cmdStatus", "cancelled")
                                                if (model.jobId) root.aiWidget.cancelJob(model.jobId)
                                            }
                                        }
                                    }
                                }

                                Row {
                                    visible: model.role === "command" && model.cmdStatus === "running"; spacing: 6
                                    Text {
                                        id: _runningIcon; text: "󰔟"; font.family: Theme.fontMono; font.pixelSize: 13; color: Theme.accent; anchors.verticalCenter: parent.verticalCenter
                                        SequentialAnimation on rotation { running: parent.visible; loops: Animation.Infinite; NumberAnimation { to: 360; duration: 900; easing.type: Easing.Linear } onStopped: _runningIcon.rotation = 0 }
                                    }
                                    Text { text: "Ejecutando…"; font.family: Theme.fontSans; font.pixelSize: 12; color: Theme.accent; anchors.verticalCenter: parent.verticalCenter }
                                }

                                Row {
                                    visible: model.role === "command" && model.cmdStatus === "cancelled"; spacing: 6
                                    Text { text: "󰜺"; font.family: Theme.fontMono; font.pixelSize: 12; color: Theme.textMuted; anchors.verticalCenter: parent.verticalCenter }
                                    Text { text: "Cancelado"; font.family: Theme.fontSans; font.pixelSize: 12; color: Theme.textMuted; anchors.verticalCenter: parent.verticalCenter }
                                }
                            }
                        }
                    }

                    // ── Mensaje de sistema ────────────────────────────────
                    Component {
                        id: sysMsgComp
                        Item {
                            implicitHeight: _sysText.implicitHeight + 4
                            width: msgDelegate.width
                            TextEdit {
                                id: _sysText
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: parent.width
                                horizontalAlignment: TextEdit.AlignHCenter
                                text: model.content
                                font.family: Theme.fontSans; font.pixelSize: 11
                                color: Theme.textMuted; opacity: 0.6
                                readOnly: true; selectByMouse: true
                            }
                        }
                    }
                } // delegate

                // Estado vacío
                Column {
                    anchors.centerIn: parent
                    visible: chatFlickable.count === 0
                    spacing: 12; opacity: 0.45
                    Text { text: "󱜚"; font.family: Theme.fontMono; font.pixelSize: 46; color: Theme.accent; horizontalAlignment: Text.AlignHCenter; anchors.horizontalCenter: parent.horizontalCenter }
                    Text {
                        text: root.aiWidget && root.aiWidget.backendReady ? "¿En qué puedo ayudarte?" : "Iniciando Minerva…"
                        font.family: Theme.fontSans; font.pixelSize: 13; color: Theme.textMuted
                        horizontalAlignment: Text.AlignHCenter; anchors.horizontalCenter: parent.horizontalCenter
                    }
                    Text { text: "Tengo acceso a tu directorio home y búsqueda web"; font.family: Theme.fontSans; font.pixelSize: 11; color: Theme.textMuted; horizontalAlignment: Text.AlignHCenter; anchors.horizontalCenter: parent.horizontalCenter }
                }
            } // ListView

        }


        // ── Barra de input ────────────────────────────────────────────────
        Rectangle {
            id: inputBar
            width:  parent.width
            height: 56
            color:  Qt.rgba(1, 1, 1, 0.03)

            Rectangle {
                anchors.top: parent.top
                width: parent.width; height: 1
                color: Qt.rgba(1, 1, 1, 0.07)
            }

            Row {
                anchors { fill: parent; margins: 8 }
                spacing: 8

                // Botón imagen
                Rectangle {
                    width:  42
                    height: parent.height
                    radius: 12
                    color: root.aiWidget && root.aiWidget.pendingImage !== ""
                        ? Qt.rgba(Theme.success.r, Theme.success.g, Theme.success.b, 0.3)
                        : (imgMa.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(1, 1, 1, 0.07))
                    Behavior on color { ColorAnimation { duration: 150 } }

                    Text {
                        anchors.centerIn: parent
                        text: "󰁦" // Icono adjuntar
                        font.family: Theme.fontMono
                        font.pixelSize: 20
                        color: root.aiWidget && root.aiWidget.pendingImage !== "" ? Theme.success : Theme.textMuted
                    }

                    MouseArea {
                        id: imgMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (root.aiWidget && root.aiWidget.pendingImage !== "") {
                                root.aiWidget.pendingImage = "" // Toggle off
                            } else if (root.aiWidget) {
                                root.aiWidget.selectImage()
                            }
                        }
                    }
                }

                // Campo de texto
                Rectangle {
                    height: parent.height
                    width:  parent.width - 150 // send + mic + image + spacings
                    radius: 12
                    color:  Qt.rgba(1, 1, 1, 0.07)
                    border.width: inputField.activeFocus ? 1 : 0
                    border.color: Theme.accent
                    Behavior on border.color { ColorAnimation { duration: 150 } }

                    TextInput {
                        id: inputField
                        anchors { fill: parent; margins: 10 }
                        font.family: Theme.fontSans
                        font.pixelSize: 13
                        color: Theme.textPrimary
                        clip: true
                        readOnly: root.aiWidget && (root.aiWidget.isThinking || root.aiWidget.isRecording || root.aiWidget.isTranscribing)

                        // Placeholder manual
                        Text {
                            visible: !inputField.text && !inputField.activeFocus
                            text: root.aiWidget && root.aiWidget.isRecording
                                ? "🎙 Escuchando… presiona de nuevo para enviar"
                                : root.aiWidget && root.aiWidget.isTranscribing
                                ? "⏳ Transcribiendo…"
                                : root.aiWidget && root.aiWidget.isThinking
                                ? "Esperando respuesta…"
                                : root.aiWidget && root.aiWidget.pendingImage !== ""
                                ? "🖼 Imagen adjunta. Escribe un mensaje…"
                                : "Escribe un mensaje…  Enter para enviar"
                            font: inputField.font
                            color: root.aiWidget && root.aiWidget.isRecording ? Theme.danger : Theme.textMuted
                            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                        }

                        onCursorPositionChanged: root.checkAutocomplete()
                        onTextChanged: root.checkAutocomplete()

                        Keys.onPressed: function(e) {
                            if (root.showSuggestions && fuzzySuggestionsModel.count > 0) {
                                if (e.key === Qt.Key_Up) {
                                    suggestionsList.currentIndex = Math.max(0, suggestionsList.currentIndex - 1)
                                    e.accepted = true
                                    return
                                }
                                if (e.key === Qt.Key_Down) {
                                    suggestionsList.currentIndex = Math.min(fuzzySuggestionsModel.count - 1, suggestionsList.currentIndex + 1)
                                    e.accepted = true
                                    return
                                }
                                if (e.key === Qt.Key_Tab || e.key === Qt.Key_Return) {
                                    var item = fuzzySuggestionsModel.get(suggestionsList.currentIndex)
                                    if (item) {
                                        root.acceptSuggestion(item.fileName, item.isDir)
                                        e.accepted = true
                                        return
                                    }
                                }
                                if (e.key === Qt.Key_Escape) {
                                    root.showSuggestions = false
                                    e.accepted = true
                                    return
                                }
                            }
                            // Delete whole chip (alias) if Backspace or Delete touches it
                            if (e.key === Qt.Key_Backspace || e.key === Qt.Key_Delete) {
                                var txt = inputField.text
                                var cpos = inputField.cursorPosition
                                for (var key in root.pathAliases) {
                                    var idx = 0
                                    while ((idx = txt.indexOf(key, idx)) !== -1) {
                                        var start = idx
                                        var end = idx + key.length
                                        if (e.key === Qt.Key_Backspace && cpos > start && cpos <= end) {
                                            inputField.text = txt.substring(0, start) + txt.substring(end)
                                            inputField.cursorPosition = start
                                            e.accepted = true
                                            return
                                        }
                                        if (e.key === Qt.Key_Delete && cpos >= start && cpos < end) {
                                            inputField.text = txt.substring(0, start) + txt.substring(end)
                                            inputField.cursorPosition = start
                                            e.accepted = true
                                            return
                                        }
                                        idx = end
                                    }
                                }
                            }
                            
                            // Convert typed directory to chip when space is pressed
                            if (e.key === Qt.Key_Space) {
                                var currentTxt = inputField.text
                                var currentCpos = inputField.cursorPosition
                                var lastAt = currentTxt.lastIndexOf("@[", currentCpos - 1)
                                if (lastAt !== -1 && currentTxt.substring(currentCpos - 1, currentCpos) === "/") {
                                    var possibleDir = currentTxt.substring(lastAt, currentCpos)
                                    if (possibleDir.indexOf(" ") === -1) {
                                        var rawPath = possibleDir.substring(2)
                                        var fullPath = ""
                                        if (rawPath.startsWith("/")) {
                                            fullPath = rawPath
                                        } else if (rawPath.startsWith("~")) {
                                            fullPath = Quickshell.env("HOME") + rawPath.substring(1)
                                        } else {
                                            fullPath = Quickshell.env("HOME") + "/" + rawPath
                                        }
                                        
                                        if (fullPath.length > 1 && fullPath.endsWith("/")) {
                                            fullPath = fullPath.substring(0, fullPath.length - 1)
                                        }
                                        
                                        var folderName = fullPath
                                        var lastSlash = fullPath.lastIndexOf('/')
                                        if (lastSlash !== -1 && lastSlash < fullPath.length - 1) {
                                            folderName = fullPath.substring(lastSlash + 1)
                                        } else if (fullPath === "/") {
                                            folderName = "root"
                                        }
                                        
                                        var dirAliasKey = root.toChipText(folderName, true)
                                        var dirCounter = 1
                                        while (root.pathAliases[dirAliasKey] && root.pathAliases[dirAliasKey] !== "@[" + fullPath + "]") {
                                            dirAliasKey = root.toChipText(folderName + " (" + dirCounter + ")", true)
                                            dirCounter++
                                        }
                                        
                                        root.pathAliases[dirAliasKey] = "@[" + fullPath + "]"
                                        
                                        var dirBefore = currentTxt.substring(0, lastAt)
                                        var dirAfter = currentTxt.substring(currentCpos)
                                        
                                        inputField.text = dirBefore + dirAliasKey + " " + dirAfter
                                        inputField.cursorPosition = (dirBefore + dirAliasKey + " ").length
                                        root.showSuggestions = false
                                        e.accepted = true
                                        return
                                    }
                                }
                            }
                            
                            if (e.key === Qt.Key_Return) {
                                if (!(e.modifiers & Qt.ShiftModifier)) {
                                    root.sendMessage()
                                    e.accepted = true
                                }
                            }
                        }
                    }
                }

                // Botón micrófono
                Rectangle {
                    width:  42
                    height: parent.height
                    radius: 12
                    color: root.aiWidget && root.aiWidget.isRecording
                        ? Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.3)
                        : (micMa.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(1, 1, 1, 0.07))
                    Behavior on color { ColorAnimation { duration: 150 } }

                    Text {
                        anchors.centerIn: parent
                        text: "󰍬" // NerdFont mic
                        font.family: Theme.fontMono
                        font.pixelSize: 20
                        color: root.aiWidget && root.aiWidget.isRecording ? Theme.danger : Theme.textMuted
                        
                        SequentialAnimation on opacity {
                            running: root.aiWidget && root.aiWidget.isRecording
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.3; duration: 600 }
                            NumberAnimation { to: 1.0; duration: 600 }
                            onStopped: opacity = 1.0
                        }
                    }

                    MouseArea {
                        id: micMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (root.aiWidget) root.aiWidget.toggleVoice()
                    }
                }

                // Botón detener TTS (silenciar voz)
                Rectangle {
                    width:   (root.aiWidget && root.aiWidget.isSpeaking) ? 42 : 0
                    height:  parent.height
                    radius:  12
                    visible: width > 0
                    clip:    true
                    color:   stopTtsMa.containsMouse 
                        ? Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.3)
                        : Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.15)
                    Behavior on width { NumberAnimation { duration: 200; easing.type: Easing.InOutQuad } }
                    Behavior on color { ColorAnimation  { duration: 150 } }

                    Text {
                        anchors.centerIn: parent
                        text: "󰝟" // NerdFont speaker off
                        font.family: Theme.fontMono
                        font.pixelSize: 18
                        color: Theme.warning
                        
                        SequentialAnimation on opacity {
                            running: root.aiWidget && root.aiWidget.isSpeaking
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.4; duration: 500 }
                            NumberAnimation { to: 1.0; duration: 500 }
                            onStopped: opacity = 1.0
                        }
                    }

                    MouseArea {
                        id: stopTtsMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (root.aiWidget) root.aiWidget.stopTTS()
                    }
                }

                // Botón enviar / spinner
                Rectangle {
                    width:  42
                    height: parent.height
                    radius: 12
                    color: sendMa.containsMouse && !(root.aiWidget && root.aiWidget.isThinking)
                        ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.25)
                        : Qt.rgba(1, 1, 1, 0.07)
                    opacity: (root.aiWidget && (root.aiWidget.isThinking || root.aiWidget.isRecording)) ? 0.4 : 1.0
                    Behavior on color   { ColorAnimation  { duration: 150 } }
                    Behavior on opacity { NumberAnimation { duration: 200 } }

                    Text {
                        id: sendIcon
                        anchors.centerIn: parent
                        text: (root.aiWidget && root.aiWidget.isThinking) ? "󰔟" : "󰒊"
                        font.family: Theme.fontMono
                        font.pixelSize: 20
                        color: Theme.accent
                        SequentialAnimation on rotation {
                            running: root.aiWidget && root.aiWidget.isThinking
                            loops: Animation.Infinite
                            NumberAnimation { to: 360; duration: 900; easing.type: Easing.Linear }
                            onStopped: sendIcon.rotation = 0
                        }
                    }

                    MouseArea {
                        id: sendMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: !(root.aiWidget && (root.aiWidget.isThinking || root.aiWidget.isRecording))
                        onClicked: root.sendMessage()
                    }
                }
            }
        }
    }

    // ── Autocomplete Overlay ──────────────────────────────────────────────
    Rectangle {
        id: suggestionsPopup
        visible: root.showSuggestions && fuzzySuggestionsModel.count > 0
        width: 320
        height: Math.min(fuzzySuggestionsModel.count * 34 + 12, 220)
        
        anchors.left: parent.left
        anchors.leftMargin: 20
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 60

        radius: 12
        color: Qt.rgba(0.08, 0.08, 0.12, 0.95)
        border.width: 1
        border.color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.5)

        layer.enabled: true

        ListView {
            id: suggestionsList
            anchors.fill: parent
            anchors.margins: 6
            model: fuzzySuggestionsModel
            clip: true
            spacing: 2
            
            delegate: Rectangle {
                width: ListView.view.width
                height: 32
                color: ListView.isCurrentItem ? Qt.rgba(1, 1, 1, 0.1) : (maSuggestion.containsMouse ? Qt.rgba(1, 1, 1, 0.05) : "transparent")
                radius: 8
                
                Row {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 10
                    Text {
                        text: model.isDir ? "󰉋" : "󰈔"
                        font.family: Theme.fontMono
                        font.pixelSize: 14
                        color: model.isDir ? Theme.accent : Theme.textMuted
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: model.fileName
                        font.family: Theme.fontSans
                        font.pixelSize: 13
                        color: Theme.textPrimary
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                
                MouseArea {
                    id: maSuggestion
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        root.acceptSuggestion(model.fileName, model.isDir)
                    }
                    onEntered: suggestionsList.currentIndex = index
                }
            }
        }
    }

    // ── Overlay de confirmación ───────────────────────────────────────────
    // Aparece para comandos destructivos o sudo, solicita confirmación explícita.
    Rectangle {
        id: confirmOverlay
        anchors.fill: parent
        visible: root.aiWidget ? root.aiWidget.showConfirm : false
        color: Qt.rgba(0, 0, 0, 0.72)

        // Entrada con animación
        opacity: visible ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: 180 } }

        // Caja del diálogo
        Rectangle {
            anchors.centerIn: parent
            width:  parent.width - 36
            height: dlgCol.implicitHeight + 44
            radius: 18
            color:  "#141422"
            border.width: 1
            border.color: Qt.rgba(0.95, 0.65, 0.2, 0.55)

            // Sombra sutil
            layer.enabled: visible

            Column {
                id: dlgCol
                anchors.centerIn: parent
                width: parent.width - 44
                spacing: 16

                // Icono + título
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 10
                    Text {
                        text: root.aiWidget && root.aiWidget.pendingIsSudo ? "󰌞" : "󰀦"
                        font.family: Theme.fontMono
                        font.pixelSize: 28
                        color: Theme.warning
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 3
                        Text {
                            text: root.aiWidget && root.aiWidget.pendingIsSudo ? "Permisos elevados" : "¿Confirmar acción?"
                            font.family: Theme.fontSans
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: Theme.warning
                        }
                    }
                }

                Text {
                    width: parent.width
                    text: root.aiWidget ? root.aiWidget.pendingReason : ""
                    font.family: Theme.fontSans
                    font.pixelSize: 12
                    color: Theme.textMuted
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
                }

                // Comando a confirmar
                Rectangle {
                    width: parent.width
                    height: dlgCmdTxt.implicitHeight + 16
                    radius: 10
                    color: Qt.rgba(0, 0, 0, 0.45)
                    border.width: 1
                    border.color: Qt.rgba(0.95, 0.65, 0.2, 0.25)

                    Text {
                        id: dlgCmdTxt
                        anchors {
                            left: parent.left; right: parent.right
                            verticalCenter: parent.verticalCenter
                            margins: 12
                        }
                        text: "$ " + (root.aiWidget ? root.aiWidget.pendingCmd : "")
                        font.family: Theme.fontMono
                        font.pixelSize: 12
                        color: Theme.warning
                        wrapMode: Text.Wrap
                    }
                }

                // Botones
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 12

                    // Cancelar
                    Rectangle {
                        width: 100; height: 36; radius: 10
                        color: dlgCancelMa.containsMouse ? Qt.rgba(0.3,0.3,0.3,0.4) : Qt.rgba(0.15,0.15,0.15,0.4)
                        border.width: 1; border.color: Qt.rgba(1,1,1,0.2)
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text {
                            anchors.centerIn: parent
                            text: "Cancelar"
                            font.family: Theme.fontSans; font.pixelSize: 13
                            color: Theme.textPrimary
                        }
                        MouseArea {
                            id: dlgCancelMa
                            anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (root.aiWidget) root.aiWidget.showConfirm = false
                        }
                    }

                    // Ejecutar de todos modos
                    Rectangle {
                        width: root.aiWidget && root.aiWidget.pendingIsSudo ? 150 : 170
                        height: 36; radius: 10
                        color: dlgExecMa.containsMouse ? Qt.rgba(0.75,0.45,0.08,0.55) : Qt.rgba(0.5,0.28,0.04,0.4)
                        border.width: 1; border.color: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.75)
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text {
                            anchors.centerIn: parent
                            text: root.aiWidget && root.aiWidget.pendingIsSudo ? "Ejecutar (pkexec)" : "Ejecutar de todos modos"
                            font.family: Theme.fontSans; font.pixelSize: 12
                            color: Theme.warning
                        }
                        MouseArea {
                            id: dlgExecMa
                            anchors.fill: parent; hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (!root.aiWidget) return
                                root.aiWidget.showConfirm = false
                                var pJobId = root.aiWidget.pendingJobId || ""
                                // Marcar la tarjeta como "running" buscando por jobId
                                for (var i = root.aiWidget.msgModel.count - 1; i >= 0; i--) {
                                    var item = root.aiWidget.msgModel.get(i)
                                    if (item.role === "command" && item.jobId === pJobId) {
                                        root.aiWidget.msgModel.setProperty(i, "cmdStatus", "running")
                                        break
                                    }
                                }
                                if (root.aiWidget.pendingIsSudo) {
                                    root.aiWidget.sudoRun(root.aiWidget.pendingCmd, pJobId)
                                } else {
                                    root.aiWidget.confirmRun(root.aiWidget.pendingCmd, pJobId)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
