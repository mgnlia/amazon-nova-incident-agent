"""Tests for the runbook TF-IDF retrieval system."""

from agent.runbooks import retrieve_runbooks, RUNBOOKS, TFIDFIndex


def test_runbooks_exist():
    assert len(RUNBOOKS) == 10


def test_all_runbooks_have_required_fields():
    for rb in RUNBOOKS:
        assert "id" in rb
        assert "title" in rb
        assert "symptoms" in rb
        assert "steps" in rb
        assert "tools_needed" in rb
        assert len(rb["steps"]) >= 2


def test_retrieve_cpu_incident():
    results = retrieve_runbooks("high CPU utilization on EC2 instance")
    assert len(results) > 0
    assert results[0]["id"] == "rb-001"


def test_retrieve_5xx_incident():
    results = retrieve_runbooks("5xx errors on load balancer")
    assert len(results) > 0
    assert results[0]["id"] == "rb-002"


def test_retrieve_database_incident():
    results = retrieve_runbooks("RDS database connection exhaustion too many connections")
    assert len(results) > 0
    assert results[0]["id"] == "rb-003"


def test_retrieve_lambda_incident():
    results = retrieve_runbooks("Lambda function timeout throttling")
    assert len(results) > 0
    assert results[0]["id"] == "rb-004"


def test_retrieve_s3_incident():
    results = retrieve_runbooks("S3 access denied 403 forbidden")
    assert len(results) > 0
    assert results[0]["id"] == "rb-005"


def test_retrieve_container_crash():
    results = retrieve_runbooks("ECS container crash loop OOMKilled")
    assert len(results) > 0
    assert results[0]["id"] == "rb-006"


def test_retrieve_dynamodb_throttle():
    results = retrieve_runbooks("DynamoDB throttling provisioned throughput exceeded")
    assert len(results) > 0
    assert results[0]["id"] == "rb-007"


def test_retrieve_network_issue():
    results = retrieve_runbooks("VPC network connectivity timeout security group")
    assert len(results) > 0
    assert results[0]["id"] == "rb-008"


def test_retrieve_top_k():
    results = retrieve_runbooks("server performance issues", top_k=5)
    assert len(results) <= 5


def test_retrieve_no_match():
    results = retrieve_runbooks("xyzzy foobar nonexistent gibberish")
    # Should still return results (TF-IDF may partially match) or empty
    assert isinstance(results, list)


def test_tfidf_index_build():
    idx = TFIDFIndex()
    idx.build(RUNBOOKS)
    assert len(idx.docs) == 10
    assert len(idx.tf_matrix) == 10
    assert len(idx.idf) > 0


def test_relevance_scores_decrease():
    results = retrieve_runbooks("CPU high utilization EC2", top_k=5)
    if len(results) >= 2:
        for i in range(len(results) - 1):
            assert results[i]["relevance_score"] >= results[i + 1]["relevance_score"]
