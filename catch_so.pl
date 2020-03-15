#!/usr/bin/perl -w
use 5.010;
use File::Copy;
use Cwd;
# 
# usage:
# chmod +x catch_so.pl
# ldd app |./catch_so.pl [ dest ]
my $dest = shift @ARGV;
$dest||=getcwd;
unless (-d $dest) {
    # body...
    $dest = getcwd
}
say $dest;
my @so_list;
while (<STDIN>) {
        # body...
        # libsodium.so.23=>/usr/lib/x86_64-linux-gnu/libsodium.so.23(0x00007fe84a3dd000)
        chomp;
        s/\s+//ig;
        say "found:$_";
        my ($name,$path) = split '=>',$_;
        if ($path && $path =~ /(.*)\(/ig){
            push @so_list,$1;    
        }
        
}    

foreach (@so_list) {
        # body...
        
        say "copy $_";
        next if /^\s+$/;
        next if $_ eq '';
        copy($_,$dest)||die "could not copy files :$!" ;
}