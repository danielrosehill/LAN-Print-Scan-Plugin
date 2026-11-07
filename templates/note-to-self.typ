// Template: Note To Self
// Variables: AGENT_NAME, MODEL_NAME, TITLE, BODY, DATE
//
// A quick note printed for the user — reminders, thoughts, or
// anything the agent thinks is worth putting on paper.

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

#text(size: 8pt, fill: luma(120))[NOTE TO SELF]

= «TITLE»

#v(0.3cm)

#text(size: 9pt, fill: luma(100))[
  From «AGENT_NAME» (`«MODEL_NAME»`) — «DATE»
]

#v(0.5cm)

#line(length: 100%, stroke: 0.3pt + luma(200))

#v(0.5cm)

«BODY»
