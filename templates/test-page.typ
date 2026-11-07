// Template: Test Page
// Variables: AGENT_NAME, MODEL_NAME, DATE, TITLE (printer name), BODY (address + ink lines)
//
// One page that proves the queue, the colour channel and the agent pipeline all work.

#set page(paper: "a4", margin: 2.5cm)
#set text(font: ("IBM Plex Sans", "DejaVu Sans"), size: 11pt)

#v(3cm)

#align(center)[
  #text(size: 28pt, weight: "bold")[I Set Up A Local AI Agent]

  #v(0.4cm)

  #text(size: 20pt)[...And All It Did Was Print]

  #v(0.2cm)

  #text(size: 28pt, weight: "bold")[This Lousy Document]

  #v(1cm)

  #grid(
    columns: 4,
    gutter: 4pt,
    rect(width: 1.5cm, height: 1.5cm, fill: rgb("#00a0e0")),
    rect(width: 1.5cm, height: 1.5cm, fill: rgb("#e0007a")),
    rect(width: 1.5cm, height: 1.5cm, fill: rgb("#ffe000")),
    rect(width: 1.5cm, height: 1.5cm, fill: black),
  )

  #v(1.5cm)

  #line(length: 60%, stroke: 0.5pt)

  #v(0.6cm)

  #text(size: 10pt, fill: luma(80))[
    Printed by *«AGENT_NAME»* (`«MODEL_NAME»`) \
    «DATE» \
    Printer: *«TITLE»*
  ]

  #v(0.4cm)

  #text(size: 10pt, fill: luma(80))[«BODY»]

  #v(0.6cm)

  #text(size: 8pt, fill: luma(120))[
    If you're reading this, the printer works. \
    If any of the four squares is missing or streaked, that cartridge needs attention.
  ]
]
