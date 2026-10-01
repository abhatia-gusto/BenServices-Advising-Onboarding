SELECT ParentId, Type, Body, CreatedDate FROM OpportunityFeed
WHERE ParentId IN (:ids) AND Type IN ('TextPost','ContentPost') ORDER BY ParentId, CreatedDate
