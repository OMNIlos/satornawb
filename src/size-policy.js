{
function applySizeEvidence(item, mode, explicitSize, chatText = null) {
  if (!item.sources || typeof item.sources !== 'object') item.sources = {}
  delete item.sources.size
  if (mode === 'none') {
    item.size = null
    item.descriptionSize = null
    item.chatText = null
    return item
  }
  if (mode === 'description') {
    item.size = explicitSize || null
    delete item.descriptionSize
    delete item.chatText
    if (item.size) item.sources.size = 'description'
    return item
  }
  delete item.size
  item.descriptionSize = explicitSize || null
  item.chatText = chatText || null
  return item
}

globalThis.SatornaAvitoSizePolicy = { applySizeEvidence }
}
