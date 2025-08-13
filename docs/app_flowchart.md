flowchart TD
    Login[User Login] --> AuthCheck{Authenticate User}
    AuthCheck -->|Valid| Dashboard[Dashboard]
    AuthCheck -->|Invalid| Error[Access Denied]
    Dashboard --> Filter[Opportunity Filtering Page]
    Filter --> List[Dynamic Opportunity List]
    List --> Select[Select Opportunity]
    Select --> Detail[Detailed Evaluation Page]
    Detail --> Analysis[AI Summaries and Ratings]
    Analysis --> QA[Compliance and QA Monitoring]
    QA --> Summary[Summary and Rating Page]
    Summary --> Final[Final Submission Page]
    Final --> Submit[Submit Proposal]
    Submit --> Confirm[Confirmation]