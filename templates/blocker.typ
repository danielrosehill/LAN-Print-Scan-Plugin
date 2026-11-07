// Template: Blocker
// Variables: AGENT_NAME, MODEL_NAME, TITLE, BODY, DATE
//
// Documents a blocker encountered during an agent session.
// Designed to be handed to a human or pinned to a board.

#set page(
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm),
  footer: context [
    #set text(size: 8pt, fill: luma(150))
    #grid(
      columns: (1fr, 1fr, 1fr),
      align: (left, center, right),
      [«AGENT_NAME» · «MODEL_NAME»],
      [«DATE»],
      [Page #counter(page).display() of #counter(page).final().first()],
    )
  ],
)
#set text(font: "IBM Plex Sans", size: 11pt)
#set par(justify: true, leading: 0.65em)

#align(center)[
  #rect(
    fill: luma(240),
    inset: 12pt,
    radius: 4pt,
    width: 100%,
  )[
    #text(size: 9pt, weight: "bold", fill: luma(80))[⚠ BLOCKER]
    #v(0.2cm)
    #text(size: 16pt, weight: "bold")[«TITLE»]
  ]
]

#v(0.5cm)

#grid(
  columns: (auto, 1fr),
  column-gutter: 1em,
  row-gutter: 0.4em,
  text(weight: "bold", size: 9pt)[Reported by:], text(size: 9pt)[«AGENT_NAME» (`«MODEL_NAME»`)],
  text(weight: "bold", size: 9pt)[Date:], text(size: 9pt)[«DATE»],
)

#v(0.5cm)

#line(length: 100%, stroke: 0.3pt + luma(200))

#v(0.5cm)

«BODY»
