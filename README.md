# PDF Outline Extractor - Adobe Hackathon

This project is a solution for Round 1A of the Adobe Hackathon, "Connecting the Dots Through Docs." The goal is to accept a PDF file and produce a structured JSON output containing the document's title and a hierarchical outline of its headings (H1, H2, H3).

## Approach and Methodology

To accurately identify headings beyond simple font size rules, this solution employs a machine learning-based approach. The pipeline is designed to be robust by analyzing a rich set of features for every line of text in the document.

The core logic follows these steps:

1.  **PDF Parsing & Feature Extraction**: The input PDF is first processed using the `PyMuPDF` library to extract all lines of text along with their properties. For each line, a comprehensive set of features is generated, including:
    *   **Font Properties**: Font size, font name, and whether the text is bold.
    *   **Positional Properties**: Indentation level and text alignment (left, center).
    *   **Content Properties**: The total length of the text, the number of digits, and the number of uppercase characters.
    *   **Structural Cues**: Whether the line is numbered (e.g., starts with "1.1") or contains a colon.

2.  **Header & Footer Filtering**: To reduce noise and improve model accuracy, a pre-processing step identifies and removes commonly repeated text from the top and bottom margins of the pages, such as running headers or page numbers.

3.  **Model-Based Heading Classification**: A pre-trained **XGBoost Classifier** model is used to classify each candidate line of text. The model, which was trained on a labeled dataset of document headings, predicts whether a line is a `H1`, `H2`, `H3`, or standard body text based on the features extracted in the first step. The trained model and its associated feature encoder are loaded from the `/models` directory.

4.  **JSON Output Generation**: Once all lines have been classified, the document's title is extracted from the first page. The identified headings are then compiled, along with their level and page number, into the required hierarchical JSON format and saved to the output directory.

## Folder Structure

```
.
├── input/
│   └── (Place input PDFs here)
├── output/
│   └── (JSON results will be generated here)
├── models/
│   ├── xgb_heading_classifier_with_text.pkl
│   └── onehot_encoder.pkl
├── main.py
├── parsing.py
├── Dockerfile
├── requirements.txt
└── README.md
```

## Running the Solution Locally

### Prerequisites

You must have Python 3.9+ installed.

### Instructions

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/nikghost17/adobe-hackathon.git
    cd adobe-hackatho
    ```

2.  **Install Dependencies**:
    Install all the required Python libraries using the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Prepare Input**:
    Place the PDF files you want to process into the `input/` directory.

4.  **Run the Script**:
    Execute the main script from the project's root directory.
    ```bash
    python main.py
    ```

5.  **Check the Output**:
    The generated JSON files, one for each input PDF, will be available in the `output/` directory.

## Docker Execution (Hackathon Submission)

To build and run the solution within the specified Docker environment, follow these steps.

1.  **Build the Docker Image**:
    Navigate to the project's root directory (where the `Dockerfile` is located) and run the build command.
    ```bash
    docker build --platform linux/amd64 -t mysolution .
    ```
    *(You can replace `mysolution` with your preferred image name).*

2.  **Run the Docker Container**:
    Use the following command to run the container. This command mounts the local `input` and `output` directories to the corresponding `/app/input` and `/app/output` directories inside the container.
    ```bash
    docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output --network none mysolution
    ```
    The container will automatically process all PDFs from the `input` folder and place the resulting `.json` files in the `output` folder before stopping.

## Libraries and Models Used

*   **Core Library**: `PyMuPDF (fitz)` for efficient PDF parsing.
*   **Machine Learning Model**: `XGBoost` for heading classification.
*   **Supporting Libraries**: `Pandas` and `Scikit-learn` for data manipulation and model handling.
