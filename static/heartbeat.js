(function () {
  const intervalMs = 60000;
  const sendHeartbeat = () => {
    const url = "/heartbeat";
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url);
      return;
    }
    fetch(url, { method: "POST", credentials: "same-origin" }).catch(() => {});
  };

  sendHeartbeat();
  setInterval(sendHeartbeat, intervalMs);
})();
