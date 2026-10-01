SELECT ContentDocumentId, ContentDocument.Title, ContentDocument.FileExtension,
       ContentDocument.CreatedDate, LinkedEntityId, SystemModstamp
FROM ContentDocumentLink WHERE LinkedEntityId IN (:ids)
