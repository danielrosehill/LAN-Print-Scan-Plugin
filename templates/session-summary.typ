// Template: Session Summary
// Variables: AGENT_NAME, MODEL_NAME, TITLE, BODY, DATE
//
// A one-page summary of what was accomplished in an AI agent session.

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

#text(size: 8pt, fill: luma(120))[SESSION SUMMARY]

= «TITLE»

#v(0.3cm)

#grid(
  columns: (auto, 1fr),
  column-gutter: 1em,
  row-gutter: 0.4em,
  text(weight: "bold", size: 9pt)[Agent:], text(size: 9pt)[«AGENT_NAME» (`«MODEL_NAME»`)],
  text(weight: "bold", size: 9pt)[Date:], text(size: 9pt)[«DATE»],
)

#v(0.5cm)

#line(length: 100%, stroke: 0.3pt + luma(200))

#v(0.5cm)

«BODY»
