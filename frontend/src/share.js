// WhatsApp bold is *text*: "*Title*" then the body, then a sign-off.
const textOf = (title, body) => [title && `*${title.trim()}*`, body, 'Sent by CopeeMachine'].filter(Boolean).join('\n\n')

export const shareWhatsApp = (title, body) =>
  window.open(`https://wa.me/?text=${encodeURIComponent(textOf(title, body))}`, '_blank', 'noopener')
