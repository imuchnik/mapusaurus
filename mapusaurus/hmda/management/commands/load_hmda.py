from csv import reader
from django.core.management.base import BaseCommand, CommandError
import os
from django import db
from geo import errors
from geo.models import Geo
from hmda.models import HMDARecord
import sys
import traceback


class Command(BaseCommand):
    args = "<path/to/20XXHMDALAR - National.csv> <delete_file:true/false> <filterhmda>"
    help = """ Load HMDA data (for all states)."""


    def handle(self, *args, **options):
        if not args:
            raise CommandError("Needs a first argument, " + Command.args)

        delete_file = False
        filter_hmda = False

        self.total_skipped = 0
        self.na_skipped = 0

        ### if delete_file argument, remove csv file after processing
        ### default is False
        ### if filter_hmda is passed in, setup known_hmda & geo_states
        ### else load all HMDA records without filtering
        if len(args) > 1:
            for arg in args:
                if  "delete_file:" in arg:
                    tmp_delete_flag= arg.split(":")
                    if tmp_delete_flag[1] == "true":
                        delete_file = True

                        print "************* CSV File(s) WiLL BE REMOVED AFTER PROCESSING ***********"

                if "filterhmda" in arg:
                    filter_hmda = True



        csv_files = []

        if os.path.isfile(args[0]):
            csv_files.append(args[0]);
        elif os.path.isdir(args[0]):
            working_directory = args[0]

            for file in os.listdir(working_directory):
                if os.path.isfile(os.path.join(working_directory,file)) and 'hmda_csv_' in file:
                    #print "CSV File: " + os.path.join(working_directory, file)
                    csv_files.append(os.path.join(working_directory, file))
        else:
            raise Exception("Not a file or Directory! " + args[0])



        geo_states = set(
                row['state'] for row in
                Geo.objects.filter(geo_type=Geo.TRACT_TYPE).values('state').distinct()
            )

        db.reset_queries()

        self.stdout.write("Filtering by states "
                              + ", ".join(list(sorted(geo_states))))

        if filter_hmda:
            known_hmda = set(
                row['statefp'] for row in
                HMDARecord.objects.values('statefp').distinct())

            self.stdout.write("Already have data for "
                             + ", ".join(list(sorted(known_hmda))))

            db.reset_queries()

        def records(self,csv_file):
            """A generator returning a new Record with each call. Required as
            there are too many to instantiate in memory at once"""
            prevent_delete= False
            datafile = open(csv_file, 'r')
            i = 0
            inserted_counter = 0
            skipped_counter = 0
            print "Processing " + csv_file
            for row in reader(datafile):
                i += 1
                if i % 50000 == 0:
                    self.stdout.write("Records Processed " + str(i) )

                try:

                    record = HMDARecord(
                        as_of_year=int(row[0]), respondent_id=row[1],
                        agency_code=row[2], loan_type=int(row[3]),
                        property_type=row[4], loan_purpose=int(row[5]),
                        owner_occupancy=int(row[6]), loan_amount_000s=int(row[7]),
                        preapproval=row[8], action_taken=int(row[9]),
                        msamd=row[10], statefp=row[11], countyfp=row[12],
                        census_tract_number=row[13], applicant_ethnicity=row[14],
                        co_applicant_ethnicity=row[15], applicant_race_1=row[16],
                        applicant_race_2=row[17], applicant_race_3=row[18],
                        applicant_race_4=row[19], applicant_race_5=row[20],
                        co_applicant_race_1=row[21], co_applicant_race_2=row[22],
                        co_applicant_race_3=row[23], co_applicant_race_4=row[24],
                        co_applicant_race_5=row[25], applicant_sex=int(row[26]),
                        co_applicant_sex=int(row[27]), applicant_income_000s=row[28],
                        purchaser_type=row[29], denial_reason_1=row[30],
                        denial_reason_2=row[31], denial_reason_3=row[32],
                        rate_spread=row[33], hoepa_status=row[34],
                        lien_status=row[35], edit_status=row[36],
                        sequence_number=row[37], population=row[38],
                        minority_population=row[39], ffieic_median_family_income=row[40],
                        tract_to_msamd_income=row[41], number_of_owner_occupied_units=row[42],
                        number_of_1_to_4_family_units=row[43], application_date_indicator=row[44])

                    censustract = row[11] + row[12] + row[13].replace('.', '')

                    record.geoid_id = errors.in_2010.get(censustract, censustract)

                    record.auto_fields()

                    if filter_hmda:
                        if (row[11] not in known_hmda and row[11] in geo_states and 'NA' not in record.geoid_id):
                            #print str(i) + "inserting: " + record.respondent_id , record.statefp , record.geoid_id
                            inserted_counter  +=1
                            yield record
                        else:
                            #print "skipping: " + str(record)
                            skipped_counter += 1
                    else:
                        if row[11] in geo_states and 'NA' not in record.geoid_id:
                            #print str(i) + "inserting: " + record.respondent_id , record.statefp , record.geoid_id
                            inserted_counter  =inserted_counter + 1
                            #if inserted_counter > 28889:
                                #print str(i) + " : " + str(inserted_counter)  + ": "+ record.sequence_number, record.respondent_id , record.statefp ,record.countyfp, record.geoid_id
                            yield record
                        else:
                            #print type(row[11])
                            #print "row11:" + row[11] + "--"
                            if row[11] in geo_states:
                                if 'NA' in record.geoid_id:
                                    self.na_skipped += 1
                                self.total_skipped +=1
                                #print str(i)+ "skipping: " + record.respondent_id , record.statefp , record.geoid_id
                            skipped_counter += 1


                except:
                    prevent_delete= True
                    print '*****************************'
                    print "Error processing csv_file"
                    print "Record Line Number " + str(i)
                    print "Row: "+ str(row)
                    print "Unexpected error:", sys.exc_info()[0]
                    print traceback.print_exc()
                    print '*****************************'

            datafile.close()

            self.stdout.write("Records Processed: " + str(i))
            self.stdout.write("Records That have been yield/Inserted: " + str(inserted_counter) )
            self.stdout.write("Records Skipped: " + str(skipped_counter) )

            if delete_file:
                if not prevent_delete:
                    os.remove(csv_file)


        window = []         # Need to materialize records for bulk_create
        total_count = 0
        for csv_file in csv_files:
            window[:] = []
            for record in records(self,csv_file):
                window.append(record)
                total_count = total_count + 1
                if len(window) > 1000:
                    HMDARecord.objects.bulk_create(window,batch_size=200)
                    window[:] = []

            if (len(window) > 0):
                print "window size (last records): " + str(len(window))
                HMDARecord.objects.bulk_create(window,batch_size=100)
                window[:] = []

            #final_count = HMDARecord.objects.filter(statefp='12').count()
            #print "Record Count after File Process" + str(final_count)
            print "Total Records bulk inserted: " + str(total_count)
            print "Total Skipped: " +str(self.total_skipped)
            print "Total geoid NA: " +str(self.na_skipped)








