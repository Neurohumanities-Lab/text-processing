library(shiny)
library(tidytext)
library(dplyr)
library(reticulate)

#charge data and run python script
corpus <- readRDS("data/corpus.rds")
source_python('data/oscScript.py')

# Define UI for application
ui <- fluidPage(

    # Application title
    titlePanel("Most Similar Sentences for a set of Words"),

    # Sidebar with a slider input for number of sentences
    #text area to enter the words
    #two action buttons: one for running the correlation, the other to obtain them separately
    sidebarLayout(
        sidebarPanel(
            sliderInput("number",
                        "Number of sentences:",
                        min = 1,
                        max = 20,
                        value = 8),
            textAreaInput("words", "Enter the set of words:"),
            actionButton("do", "Run !"),
            actionButton("add", "Next !")
        ),

        # Show a a table and a space for text
        mainPanel(
          tableOutput("textPlot"),
          textOutput("sentence")
        )
    )
)

# Define server logic for plotting and for OSC sending
server <- function(input, output, session) {
  
  #create a function to calculate jaccard similarity between sentences
  jaccard_similarity <- function(set1, set2) {
    intersection <- length(intersect(set1, set2))
    union <- length(union(set1, set2))
    return(intersection / union)
  }
  
  query_words <- reactive({input$words |> as_tibble() |> unnest_tokens(words, value) |> pull(words)
  })
  
  # Calculate Jaccard similarity for each paragraph
    similarities <- eventReactive(input$do, {
      sapply(corpus$sentence, function(paragraph) {
        paragraph_words <- unlist(strsplit(paragraph, " "))
        jaccard_similarity(query_words(), paragraph_words)}
        )})
  
    #obtain the more similar sentences with the selected query words
    tops <-reactive({corpus %>% 
        filter(sentence%in% names(tail(sort(similarities()),input$number)))
      }
      )
    
    #plot the table
    output$textPlot <- renderTable({
      tops()
      }
      )
    
    #create a counter for the Next buttton
    counter <- reactiveValues(countervalue = 0) # Defining & initializing the reactiveValues object
    
    #observe the Next button and restart it when it reaches the length of the input$number
    observeEvent(input$add, {
      counter$countervalue <- counter$countervalue + 1     # if the add button is clicked, increment the value by 1 and update it
      if(counter$countervalue>input$number) {
        counter$countervalue <- 1
        } 
      })
    
    #create a reactive value for the creatiion of the single text extracted from the table
    envio <- reactive(tops() [counter$countervalue,] %>% 
                        mutate(result=paste0(sentence,"\n",  " (", document, ", ", Year, ")")) %>% 
                        pull(result)
                      )
    
    #renderizar el texto extraído en el panel de shiny
    output$sentence <- renderText({
      envio()
      }
      )
    
    #sent the single text by OSC with the python function "enviar"
    observe({
      input_value <- envio()
      py$enviar(input_value)
      }
    )
    
    }

# Run the application 
shinyApp(ui = ui, server = server)
