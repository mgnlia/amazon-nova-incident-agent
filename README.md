# Amazon Nova Incident Commander 🚨

**AI-powered DevOps incident response agent using Amazon Nova on AWS Bedrock**

Built for the [Amazon Nova AI Challenge — Agentic AI Track](https://devpost.com/software/amazon-nova-incident-commander).

## What It Does

An autonomous incident response agent that diagnoses and remediates AWS infrastructure incidents using an **agentic tool-use loop** powered by Amazon Nova (Pro/Lite) on Bedrock.

### Key Features

- **Agentic Tool-Use Loop**: Full `converse → toolUse → toolResult → converse` cycle with Amazon Nova via Bedrock's Converse API
- **10 Built-in Runbooks**: TF-IDF retrieval-augmented generation (RAG) matches incidents to standard operating procedures
- **7 Diagnostic Tools**: CloudWatch metrics, log search, SSM commands, network analysis, IAM policy review, SQL queries, and runbook retrieval
- **Multi-turn Reasoning**: Agent autonomously decides which tools to call, analyzes results, and iterates up to 15 turns
- **Auto-fallback**: Automatically falls back from Nova Pro to Nova Lite on throttling
- **REST API**: FastAPI backend for incident submission, tracking, and demo mode

## Architecture

```
User → FastAPI API → Agent Core (agentic loop)
                         ↓
                    Amazon Nova (Bedrock Converse API)
                         ↓
                    Tool Selection → Tool Execution
                         ↓              ↓
                    CloudWatch    Log Search    SSM
                    DynamoDB     IAM Policy    Network
                         ↓
                    Runbook RAG (TF-IDF)
                         ↓
                    Diagnosis + Remediation
```

## Quick Start

```bash
# Install dependencies
uv sync

# Run in mock mode (no AWS credentials needed)
MOCK_MODE=true uv run uvicorn api.main:app --reload

# Run with real Bedrock
AWS_REGION=us-east-1 uv run uvicorn api.main:app --reload
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/incidents` | Submit incident for analysis |
| GET | `/incidents` | List all analyses |
| GET | `/incidents/{id}` | Get specific analysis |
| POST | `/demo` | Run demo incident |

### Example Request

```bash
curl -X POST http://localhost:8000/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Production API returning 5xx errors at 200/min, 2 of 5 ALB targets unhealthy",
    "severity": "critical",
    "service": "ALB",
    "use_mock": true
  }'
```

## Runbooks

| ID | Incident Type |
|----|--------------|
| rb-001 | High CPU / Memory on EC2 |
| rb-002 | 5xx Errors on ALB / API Gateway |
| rb-003 | Database Connection Exhaustion (RDS) |
| rb-004 | Lambda Throttling / Timeout |
| rb-005 | S3 Access Denied / Bucket Policy |
| rb-006 | ECS/EKS Task Crash Loop |
| rb-007 | DynamoDB Throttling |
| rb-008 | VPC / Network Connectivity Failure |
| rb-009 | CloudFront Cache Miss / Origin Error |
| rb-010 | IAM / STS Credential Failure |

## Testing

```bash
uv run pytest tests/ -v
```

## Tech Stack

- **AI Model**: Amazon Nova Pro v1 / Lite v1 on AWS Bedrock
- **API Framework**: FastAPI + Uvicorn
- **RAG**: Custom TF-IDF retrieval over runbook corpus
- **Language**: Python 3.11+
- **Package Manager**: uv
- **CI**: GitHub Actions

## How It Uses Amazon Nova

1. **Converse API**: Uses Bedrock's `converse()` with `toolConfig` for native tool-use
2. **Multi-turn**: Agent loops autonomously — Nova decides which tools to call
3. **System Prompt Engineering**: Structured incident commander persona with prioritization logic
4. **Fallback**: Auto-switches Nova Pro → Lite on throttling for resilience

## License

MIT
