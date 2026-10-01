{
  function extract(text) {
    const value = String(text || '')
    const pickup = /возврат[^.!?]{0,80}(?:можно забрать|готов к (?:получению|выдаче))|(?:можно забрать|заберите)[^.!?]{0,80}возврат/iu.test(value)
    const inbound = /возврат[^.!?]{0,80}(?:едет обратно|в пути)|(?:едет обратно|в пути)[^.!?]{0,80}возврат/iu.test(value)
    const code = value.match(/(?:код получения возврата|код возврата)[ \t]*[:№—-][ \t]*([A-ZА-ЯЁ0-9-]*\d[A-ZА-ЯЁ0-9-]*(?:[ \t]+\d[A-ZА-ЯЁ0-9-]*){0,3})/iu)?.[1] || null
    return {
      status: pickup && !inbound ? 'ready_for_pickup' : inbound && !pickup ? 'in_transit' : null,
      pickupCode: code,
    }
  }

  globalThis.SatornaAvitoReturnDetails = { extract }
}
