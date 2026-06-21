def migrate(cr, version):
    cr.execute(
        """
        UPDATE realestate_unit
           SET tax_classification = CASE
               WHEN unit_type IN ('flat', 'room') THEN 'residential'
               WHEN unit_type IN ('office', 'shop') THEN 'commercial'
               ELSE tax_classification
           END
         WHERE tax_classification IS NULL
        """
    )
