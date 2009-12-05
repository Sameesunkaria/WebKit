description("Web Socket send test");

if (window.layoutTestController)
    layoutTestController.waitUntilDone();

function endTest()
{
    isSuccessfullyParsed();
    clearTimeout(timeoutID);
    if (window.layoutTestController)
        layoutTestController.notifyDone();
}

var ws = new WebSocket("ws://localhost:8880/websocket/tests/send");

var FIRST_MESSAGE_TO_SEND = "This is the first message to send to the server.";
var SECOND_MESSAGE_TO_SEND = "This is the second.";
// data needs to be global to be accessbile from shouldBe().
var data = "";

ws.onopen = function()
{
    debug("Connected.");
    ws.send(FIRST_MESSAGE_TO_SEND);
};

ws.onmessage = function(messageEvent)
{
    // The server should echo back the first message.
    data = messageEvent.data;
    shouldBe("data", "FIRST_MESSAGE_TO_SEND");
    ws.onmessage = function(messageEvent) {
        // The server should echo back the second message.
        data = messageEvent.data;
        shouldBe("data", "SECOND_MESSAGE_TO_SEND");
    };
    ws.send(SECOND_MESSAGE_TO_SEND);
};

ws.onclose = function()
{
    debug("Closed.");
    endTest();
};

function timeOutCallback()
{
    testFailed("Timed out in state: " + ws.readyState);
    endTest();
}

var timeoutID = setTimeout(timeOutCallback, 3000);

var successfullyParsed = true;
