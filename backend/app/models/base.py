"""Base PynamoDB model with single-table design."""
import os
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute,
    NumberAttribute,
    UTCDateTimeAttribute,
    BooleanAttribute,
    MapAttribute,
    ListAttribute,
)
from pynamodb.indexes import GlobalSecondaryIndex, AllProjection


class GSI1Index(GlobalSecondaryIndex):
    """GSI1 for secondary access patterns."""
    class Meta:
        index_name = "GSI1"
        projection = AllProjection()
        billing_mode = "PAY_PER_REQUEST"
    GSI1PK = UnicodeAttribute(hash_key=True)
    GSI1SK = UnicodeAttribute(range_key=True)


class GSI2Index(GlobalSecondaryIndex):
    """GSI2 for tertiary access patterns."""
    class Meta:
        index_name = "GSI2"
        projection = AllProjection()
        billing_mode = "PAY_PER_REQUEST"
    GSI2PK = UnicodeAttribute(hash_key=True)
    GSI2SK = UnicodeAttribute(range_key=True)


class BaseModel(Model):
    """Base model using single-table design pattern.
    
    PK (partition key) and SK (sort key) are used for all entities.
    GSI1PK/GSI1SK for secondary access patterns.
    """

    class Meta:
        table_name = os.getenv("DYNAMODB_TABLE_NAME", "skyeye-dev")
        region = os.getenv("AWS_REGION", "us-east-1")
        billing_mode = "PAY_PER_REQUEST"
        # When running in Lambda, credentials come from the execution role
        # For local dev, use AWS_PROFILE
        if os.getenv("AWS_PROFILE"):
            from botocore.session import Session
            aws_session = Session(profile=os.getenv("AWS_PROFILE"))

    # Primary key
    PK = UnicodeAttribute(hash_key=True)
    SK = UnicodeAttribute(range_key=True)

    # GSI1 for secondary access patterns
    gsi1_index = GSI1Index()
    GSI1PK = UnicodeAttribute(null=True)
    GSI1SK = UnicodeAttribute(null=True)

    # GSI2 for tertiary access patterns
    gsi2_index = GSI2Index()
    GSI2PK = UnicodeAttribute(null=True)
    GSI2SK = UnicodeAttribute(null=True)

    # Common fields
    entity_type = UnicodeAttribute()
    created_at = UnicodeAttribute()
    updated_at = UnicodeAttribute()
    created_by = UnicodeAttribute(null=True)
    updated_by = UnicodeAttribute(null=True)


class AttachmentMap(MapAttribute):
    """Attachment metadata stored as a map attribute."""
    file_id = UnicodeAttribute()
    file_name = UnicodeAttribute()
    file_type = UnicodeAttribute()  # pdf, image, word, cad
    file_size = NumberAttribute()
    s3_key = UnicodeAttribute()
    upload_time = UnicodeAttribute()
    uploaded_by = UnicodeAttribute(null=True)


class PaymentNodeMap(MapAttribute):
    """Payment schedule node."""
    node_name = UnicodeAttribute()  # e.g., "预付款", "进度款", "尾款"
    percentage = NumberAttribute()
    amount = NumberAttribute()
    planned_date = UnicodeAttribute(null=True)
    actual_date = UnicodeAttribute(null=True)
    status = UnicodeAttribute(default="pending")  # pending, paid
