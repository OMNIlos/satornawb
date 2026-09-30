{
  // Only an explicit dispatch instruction may supply this value. A tracking
  // code, phone, order ID or barcode elsewhere in the card is not equivalent.
  function extract(text) {
    const values = [...String(text || '').matchAll(/(?:на месте назовите[ \t]+)?номер[ \t]+отправления[ \t]*[:№—-][ \t]*([A-ZА-ЯЁ0-9-]*\d[A-ZА-ЯЁ0-9-]*(?:[ \t]+\d[A-ZА-ЯЁ0-9-]*){0,4})/giu)]
      .map((match) => match[1].replace(/[ \t]+/g, ' ').trim())
      .filter((value) => value.length >= 4 && value.length <= 40)
    const unique = [...new Set(values)]
    return { number: unique.length === 1 ? unique[0] : null, state: unique.length > 1 ? 'ambiguous' : unique.length ? 'confirmed' : 'missing' }
  }

  globalThis.SatornaAvitoShipmentNumber = { extract }
}
